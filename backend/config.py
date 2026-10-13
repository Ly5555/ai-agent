"""项目配置（环境变量驱动）。

把密钥/地址放到 backend/.env，或直接用环境变量注入（docker-compose 已配）。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "个人知识库 Agent"

    # LLM 网关配置（默认 GLM-4-flash，可换成 OpenAI / 其他兼容网关）
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    llm_model: str = "glm-4-flash"

    # 向量模型（与 chat 同网关同 Key）
    embedding_model: str = "embedding-3"

    # LLM/Embedding 客户端是否走系统代理。默认 False=直连：智谱 open.bigmodel.cn 是国内站，
    # 直连更稳；避免终端里 Clash/_autoproxy 把国内 API 导去连不通的代理导致 Connection error。
    # 若换成国外网关需代理，设 LLM_TRUST_ENV_PROXY=true。
    llm_trust_env_proxy: bool = False

    # 允许跨域的前端来源（开发期 Vite 默认端口 5173）
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()


def make_http_client():
    """构建给 OpenAI/Embedding 客户端用的 httpx.Client。

    默认 trust_env=False：忽略 HTTP(S)_PROXY 环境变量、直连目标（适配国内智谱网关）。
    settings.llm_trust_env_proxy=True 时改为尊重系统代理（换国外网关时用）。
    """
    import httpx

    return httpx.Client(trust_env=settings.llm_trust_env_proxy)
