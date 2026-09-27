// 后端 API 调用封装
// TODO: 用 fetch / axios 封装 /chat、/health 等接口
const BASE_URL = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

// export async function chat(query: string) {
//   const res = await fetch(`${BASE_URL}/chat`, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({ query }),
//   });
//   return res.json();
// }
