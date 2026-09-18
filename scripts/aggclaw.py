"""
AppGrowing Global 出海游戏报告 - aggclaw API 客户端

aggclaw 本身是自主分析 agent:调用时只传一个问题(input),
其内部 agent 自行检索素材、决定分析维度并输出完整分析,无需预设参数。

用途:
- 调用 aggclaw 素材洞察(单次或同问题多次调用做交叉验证,chat_mode 7=游戏)
- 获取 session 关联素材清单(materials 接口)
- 素材链接格式化(appgrowing-global 详情页)
"""
import os
import re
import json
import sys
import time
from urllib import request, error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# aggclaw API 配置
AGGCLAW_API_URL = "https://ai-chat-global.youcloud.com/aichat/claw"
MATERIALS_API_TPL = "https://ai-chat-global.youcloud.com/aichat/sessions/{session_id}/materials"
REQUEST_TIMEOUT = 600  # 秒,完整分析需要 1-8 分钟,绝对不可缩短(提前中断会返回空结果)
MAX_RETRIES = 10       # 最大重试次数,报错/超时/空结果立即重试

# 素材详情页域名(AppGrowing Global)
MATERIAL_DETAIL_HOST = "https://appgrowing-global.youcloud.com/material"


def get_api_key() -> str:
    """从环境变量获取 API Key(优先 YOUCLOUD_API_KEY)"""
    for env_name in ["YOUCLOUD_API_KEY", "COZE_YOUCLOUD_API_KEY"]:
        key = os.getenv(env_name)
        if key:
            return key
    raise ValueError("未找到 YOUCLOUD_API_KEY,请先配置(AppGrowing Global → 个人中心 → 企业信息)")


def call_aggclaw(prompt: str, chat_mode: int = 7, language_code: str = "zh",
                 session_id: str = "", timeout: int = REQUEST_TIMEOUT) -> dict:
    """
    调用 aggclaw 自主分析 agent(单次调用,含强制重试)

    参数:
        prompt: 用户问题(保持原始措辞,可附时间线/品类/地区等必要背景;
                分析维度由 aggclaw 内部 agent 自行决定,不预设结构)
        chat_mode: 7=游戏, 8=非游戏/短剧, 9=灵感
        language_code: zh/ja/en(仅新会话传;复用 session 时省略)
        session_id: 新分析传 "";追问复用已有 session(此时省略 chat_mode/language_code)
        timeout: 超时秒数,默认 600,禁止缩短

    返回:
        {
            "success": True,
            "session_id": "会话ID(跟进/取素材清单用)",
            "content": "完整分析内容(output)",
            "material_ids": ["素材ID列表"]
        }
    """
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {"input": prompt}
    if session_id:
        payload["session_id"] = session_id
    else:
        payload["chat_mode"] = chat_mode
        if language_code:
            payload["language_code"] = language_code

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = request.Request(
                AGGCLAW_API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            content = data.get("output", "") or ""
            session_id_out = data.get("session_id", "")

            # 过滤错误/空结果:无实质内容(仅标题/纯欢迎语)一律重试
            if (not content or len(content.strip()) < 50
                    or "系统出错" in content or "请稍后再试" in content
                    or re.fullmatch(r"[\s\S]{0,120}", content.strip())):
                print(f"[aggclaw] 返回无效(长度={len(content)}), 重试 {attempt}/{MAX_RETRIES}")
                time.sleep(5)
                continue

            material_ids = extract_material_ids(content)

            return {
                "success": True,
                "session_id": session_id_out,
                "content": content,
                "material_ids": material_ids,
                "raw_data": data
            }

        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")[:200]
            print(f"[aggclaw] HTTP {e.code}: {body}, 重试 {attempt}/{MAX_RETRIES}")
            time.sleep(5)
        except error.URLError as e:
            print(f"[aggclaw] 请求异常: {e}, 重试 {attempt}/{MAX_RETRIES}")
            time.sleep(5)
        except Exception as e:
            print(f"[aggclaw] 未知异常: {e}, 重试 {attempt}/{MAX_RETRIES}")
            time.sleep(5)

    raise Exception(f"aggclaw API 调用失败,已重试 {MAX_RETRIES} 次")


def call_cross_validation(prompt: str, times: int = 3, chat_mode: int = 7,
                          language_code: str = "zh") -> list:
    """
    同一问题多次调用做交叉验证(每次独立 session,取不同素材样本)

    置信度规则:times 次调用中 ≥2 次结论一致 → 高置信度;仅 1 次 → 潜在机会点。
    (完整规则见 references/交叉验证与洞察历史.md)

    参数:
        prompt: 用户问题(多次调用使用同一问题,不预设分析参数)
        times: 调用次数(行业周报/月报=5,品类洞察/单品深度=3,样本偏少=2)
    返回: [call_aggclaw 结果, ...],全部成功才返回;失败抛异常
    """
    results = []
    for i in range(times):
        print(f"[aggclaw] 交叉验证 第{i+1}/{times}次")
        results.append(call_aggclaw(prompt, chat_mode=chat_mode,
                                    language_code=language_code, session_id=""))
    return results


def fetch_session_materials(session_id: str, timeout: int = 120) -> list:
    """
    获取某次分析会话关联的素材清单

    URL: GET /aichat/sessions/{session_id}/materials
    注意: session_id 中的 '=' 编码为 %3D,保留 '~'

    返回: [{"id": str, "detail_url": str, "download_url": str, "is_mentioned": bool}, ...]
    """
    api_key = get_api_key()
    encoded = session_id.replace("=", "%3D")
    url = MATERIALS_API_TPL.format(session_id=encoded)
    req = request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def extract_material_ids(content: str) -> list:
    """
    从 aggclaw 输出中提取素材ID(去重,保序)

    AGG 素材ID 两种形态:
    1. 32位hex + "-" + 3位类型: 562a8f35f5c1c8de6d2a8154e7c1e71f-202
    2. 详情页URL: appgrowing-global.youcloud.com/material/{id}-{type}
    """
    ids = []
    # 先抓详情页 URL 中的 ID
    for m in re.finditer(r'appgrowing-global\.youcloud\.com/material/([0-9a-f]{32}-\d{3})', content):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    # 再抓裸 ID(避免重复)
    for m in re.finditer(r'(?<![0-9a-f])([0-9a-f]{32}-\d{3})(?![0-9a-f])', content):
        if m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def format_material_url(material_id: str) -> str:
    """素材ID → 详情页URL: appgrowing-global.youcloud.com/material/{id}-{type}"""
    return f"{MATERIAL_DETAIL_HOST}/{material_id}"


def format_material_display(material_id: str) -> str:
    """素材ID → 短ID显示文本(取前7位,如 562a8f3)"""
    return material_id[:7] if len(material_id) >= 7 else material_id


if __name__ == "__main__":
    import sys
    # 快速自检: python aggclaw_client.py "分析SLG品类近7天在欧美的投放趋势"
    question = sys.argv[1] if len(sys.argv) > 1 else "简要介绍你能做什么"
    r = call_aggclaw(question, timeout=90)
    print("session_id:", r["session_id"])
    print("素材ID数:", len(r["material_ids"]))
    print(r["content"][:800])
