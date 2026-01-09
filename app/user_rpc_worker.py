#users_service/app/user_rpc_worker.py
import aio_pika
import asyncio
import os
import json

from app.database import SessionLocal
from app.models import User

RABBIT_URL = os.getenv("RABBIT_URL")
EXCHANGE = "topic_logs"

async def process_message(msg: aio_pika.IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body.decode())
        print(f"[user_rpc_worker] Received {msg.routing_key}: {data}")

        db = SessionLocal()
        try:
            user_id = data.get("user_id")
            user = db.get(User, user_id)

            if not user:
                response = {"ok": False}
            else:
                response = {
                    "ok": True,
                    "user": {
                        "id": user.id,
                        "name": user.name
                    }
                }

        except Exception as e:
            print("ERROR:", e)
            response = {"ok": False}
        finally:
            db.close()

        if msg.reply_to and msg.correlation_id:
            await msg.channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(response).encode(),
                    correlation_id=msg.correlation_id
                ),
                routing_key=msg.reply_to
            )

async def main():
    connection = await aio_pika.connect_robust(RABBIT_URL)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC)
    queue = await channel.declare_queue("rpc.users.get", durable=True)

    await queue.bind(exchange, routing_key="users.get")

    print("[user_rpc_worker] Listening for users.get")

    await queue.consume(process_message)
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
