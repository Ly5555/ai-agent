# Python 学习笔记

## JSON 文件读写

JSON 适合保存结构化配置和简单数据。读取 JSON 文件时，使用 `json.load(file)`；写入时，使用 `json.dump(data, file, ensure_ascii=False, indent=2)`。

文件操作建议使用 `with open(..., encoding="utf-8") as file`，这样文件会在操作结束后自动关闭。处理外部 JSON 时，应捕获 `json.JSONDecodeError`，并提示文件格式有误。

## 函数与类型标注

函数应保持单一职责。为参数和返回值补充类型标注，可以让编辑器更早发现调用错误，例如 `def load_config(path: str) -> dict: ...`。

## 异步请求

网络请求通常是 I/O 密集型任务。使用 `async def` 定义协程，在调用前使用 `await` 等待结果；需要同时请求多个接口时，可使用 `asyncio.gather` 并发执行。
