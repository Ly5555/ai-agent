"""项目配置（环境变量驱动）。

把密钥/地址放到 backend/.env，或直接用环境变量注入（docker-compose 已配）。
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Knowledge Agent"

    # LLM 网关配置（默认 GLM-4-flash，可换成 OpenAI / 其他兼容网关）
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    llm_model: str = "glm-4-flash"

    # 向量模型（与 chat 同网关同 Key）
    embedding_model: str = "embedding-3"

    # 允许跨域的前端来源（开发期 Vite 默认端口 5173）
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
