FROM node:22.4.0-alpine3.20

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

EXPOSE 3000

RUN npm run build
CMD [ "npm", "run", "start" ]