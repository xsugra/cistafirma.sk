# Pinned to a Node 20 patch release so the bundled npm (10.x) stays fixed.
# The dev container runs `npm install` on every start against a bind-mounted
# repo, so a floating tag could rewrite package-lock.json with a different npm
# version's formatting and leave the working tree permanently dirty.
FROM node:20.20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["sh", "-c", "npm run dev -- --host 0.0.0.0 --port 5173"]

