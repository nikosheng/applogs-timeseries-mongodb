import os
import random
import datetime
import certifi

from faker import Faker
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, ServerSelectionTimeoutError


def load_config():
    load_dotenv()
    return {
        "mongo_uri": os.getenv("MONGODB_URI"),
        "db_name": os.getenv("DB_NAME"),
        "coll_name": os.getenv("COLL_NAME"),
        "time_field": os.getenv("TIME_FIELD"),
        "meta_field": os.getenv("META_FIELD"),
    }


def get_mongo_client(mongo_uri):
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        # The ping command is cheap and does not require auth.
        client.admin.command('ping')
        print("MongoDB connection successful!")
        return client
    except ServerSelectionTimeoutError as err:
        print(err)
        return None


def ensure_timeseries_collection(db, coll_name, time_field, meta_field):
    try:
        db.create_collection(
            coll_name,
            timeseries={
                "timeField": time_field,
                "metaField": meta_field,
                "granularity": "seconds",
            },
            expireAfterSeconds=60 * 60 * 24 * 30,  # Data expires after 30 days
        )
        print(f"Time-series collection '{coll_name}' created.")
    except CollectionInvalid:
        print(f"Collection '{coll_name}' already exists or is not a time-series collection.")
    except Exception as e:
        print(f"Error ensuring time-series collection: {e}")


def ensure_meta_indexes(collection):
    try:
        idx_app = collection.create_index([("meta.app", 1)])
        idx_host = collection.create_index([("meta.host", 1)])
        idx_env = collection.create_index([("meta.env", 1)])
        idx_level = collection.create_index([("level", 1)])
        print(f"Ensured indexes: {idx_app}, {idx_host}, {idx_env}, {idx_level}")
    except Exception as e:
        print(f"Error creating meta indexes: {e}")


def build_log_document(fake, app_name, host, env, timestamp):
    log_level = random.choice(["INFO", "DEBUG", "WARN", "ERROR", "FATAL"])
    logger_name = random.choice(
        [
            "com.example.service.UserService",
            "com.example.repository.ProductRepository",
            "com.example.controller.OrderController",
            "org.springframework.web.servlet.DispatcherServlet",
        ]
    )
    thread_name = random.choice(["http-nio-8080-exec-1", "http-nio-8080-exec-2", "task-scheduler-1"])

    message = fake.sentence()
    uri = fake.uri_path()
    method = random.choice(["GET", "POST", "PUT", "DELETE"])
    status = random.choice([200, 201, 400, 401, 403, 404, 500, 502])
    latency = random.randint(10, 2000)

    doc = {
        "timestamp": timestamp,
        "meta": {
            "app": app_name,
            "host": host,
            "env": env,
        },
        "level": log_level,
        "logger": logger_name,
        "thread": thread_name,
        "message": message,
        "uri": uri,
        "method": method,
        "status": status,
        "latency_ms": latency,
        "traceId": fake.uuid4(),
        "spanId": fake.uuid4(),
    }

    if log_level in ["ERROR", "FATAL"] and random.random() < 0.7:
        doc["stack"] = fake.text(max_nb_chars=500)

    return doc


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate and insert Spring Boot-style logs into MongoDB.")
    parser.add_argument("--count", type=int, default=1000, help="Number of logs to generate.")
    parser.add_argument("--apps", nargs='+', default=["my-app"], help="List of application names.")
    parser.add_argument("--hosts", nargs='+', default=["host-1"], help="List of hostnames.")
    # Prefer --envs for multiple environments; keep --env for compatibility
    parser.add_argument("--envs", nargs='+', default=None, help="List of environments (e.g., dev staging prod).")
    parser.add_argument("--env", type=str, default=None, help="Single environment (deprecated; use --envs).")
    parser.add_argument("--time-dist", type=str, default="uniform", choices=["uniform", "recent"], help="Time distribution of logs.")

    args = parser.parse_args()

    config = load_config()
    mongo_uri = config["mongo_uri"]
    db_name = config["db_name"]
    coll_name = config["coll_name"]
    time_field = config["time_field"]
    meta_field = config["meta_field"]

    if not all([mongo_uri, db_name, coll_name, time_field, meta_field]):
        print("Error: Missing one or more MongoDB configuration variables in .env")
        return

    client = get_mongo_client(mongo_uri)
    if not client:
        print("Failed to connect to MongoDB. Exiting.")
        return

    db = client[db_name]
    ensure_timeseries_collection(db, coll_name, time_field, meta_field)
    collection = db[coll_name]
    # Create indexes on meta fields for efficient filtering
    ensure_meta_indexes(collection)

    fake = Faker()
    logs = []
    # Resolve environments once
    envs = args.envs if args.envs else ([args.env] if args.env else ["dev"])  # default to dev
    for i in range(args.count):
        app_name = random.choice(args.apps)
        host = random.choice(args.hosts)
        env_val = random.choice(envs)

        if args.time_dist == "recent":
            # Generate logs mostly from the last hour, with some older ones
            if random.random() < 0.8:  # 80% recent
                timestamp = datetime.datetime.now() - datetime.timedelta(seconds=random.randint(0, 3600))
            else:  # 20% older
                timestamp = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 7), seconds=random.randint(0, 86400))
        else:  # uniform distribution over the last 7 days
            timestamp = datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 7), seconds=random.randint(0, 86400))

        log_doc = build_log_document(fake, app_name, host, env_val, timestamp)
        logs.append(log_doc)

    if logs:
        try:
            collection.insert_many(logs)
            print(f"Inserted {len(logs)} logs into {db_name}.{coll_name}")
        except Exception as e:
            print(f"Error inserting logs: {e}")

    client.close()


if __name__ == "__main__":
    main()