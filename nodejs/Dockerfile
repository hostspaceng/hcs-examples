FROM node:22.4.0-alpine3.20

WORKDIR /app

COPY . /app/

RUN npm install

EXPOSE 3000

CMD [ "npm", "run", "start" ]