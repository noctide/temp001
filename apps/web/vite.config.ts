import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发时 /api 转到本机主程序（uv run uvicorn titanloom.main:app）
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
