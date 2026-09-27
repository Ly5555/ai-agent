"""FastAPI 入口。

启动：uvicorn app.main:app --reload
接口文档：http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Knowledge Agent", version="0.1.0")

# 允许前端跨域（开发期 localhost:5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# TODO: 接入 LangGraph Agent
# from app.agents.graph import build_graph
# @app.post("/chat")
# async def chat(query: str):
#     graph = build_graph()
#     result = await graph.ainvoke({"query": query})
#     return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
