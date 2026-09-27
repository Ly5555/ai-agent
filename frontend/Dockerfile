FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
# 开发模式由 docker-compose 的 command 覆盖
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
