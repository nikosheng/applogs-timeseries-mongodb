import os
import datetime
import math
import certifi

from dotenv import load_dotenv
from flask import Flask, render_template, request
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError


def create_app():
    app = Flask(__name__)
    PAGE_SIZE = 50

    def get_mongo_client():
        load_dotenv()
        mongo_uri = os.getenv("MONGODB_URI")
        try:
            client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
            # The ping command is cheap and does not require auth.
            client.admin.command('ping')
            print("MongoDB connection successful!")
            return client
        except ServerSelectionTimeoutError as err:
            print(err)
            return None

    def parse_datetime_string(dt_str):
        if not dt_str:
            return None
        try:
            return datetime.datetime.strptime(dt_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                return datetime.datetime.strptime(dt_str, '%Y-%m-%d')
            except ValueError:
                return None

    @app.route('/')
    def home():
        return render_template(
            'index.html',
            results=[],
            error="",
            app="",
            host="",
            env="",
            level="",
            start="",
            end="",
            page=1,
            total=0,
            total_pages=0,
            page_size=PAGE_SIZE,
            has_prev=False,
            has_next=False,
            prev_page=None,
            next_page=None,
        )

    @app.route('/search', methods=['GET'])
    def search():
        client = get_mongo_client()
        if not client:
            # Preserve form values on error so the user can adjust and retry
            return render_template(
                'index.html',
                results=[],
                error="Failed to connect to MongoDB. Check connection string and ensure certifi is installed.",
                app=request.args.get('app', ''),
                host=request.args.get('host', ''),
                env=request.args.get('env', ''),
                level=request.args.get('level', ''),
                start=request.args.get('start', ''),
                end=request.args.get('end', ''),
                page=int(request.args.get('page', '1') or 1),
                total=0,
                total_pages=0,
                page_size=PAGE_SIZE,
                has_prev=False,
                has_next=False,
                prev_page=None,
                next_page=None,
            )

        db_name = os.getenv("DB_NAME")
        coll_name = os.getenv("COLL_NAME")

        db = client[db_name]
        collection = db[coll_name]

        app_val = request.args.get('app', '')
        host_val = request.args.get('host', '')
        env_val = request.args.get('env', '')
        level_val = request.args.get('level', '')
        start_time_str = request.args.get('start', '')
        end_time_str = request.args.get('end', '')

        start_time = parse_datetime_string(start_time_str)
        end_time = parse_datetime_string(end_time_str)

        # Parse and normalize page
        try:
            page = int(request.args.get('page', '1') or 1)
        except ValueError:
            page = 1
        if page < 1:
            page = 1

        # Build match criteria for all filters
        match_criteria = {}
        if level_val:
            match_criteria["level"] = level_val
        if start_time or end_time:
            time_criteria = {}
            if start_time:
                time_criteria["$gte"] = start_time
            if end_time:
                time_criteria["$lte"] = end_time
            match_criteria["timestamp"] = time_criteria

        # Meta filters
        if app_val:
            match_criteria["meta.app"] = app_val
        if host_val:
            match_criteria["meta.host"] = host_val
        if env_val:
            match_criteria["meta.env"] = env_val

        # Count total matching documents for pagination
        try:
            total_docs = 0
            total_docs = db[coll_name].count_documents(match_criteria if match_criteria else {})
        except Exception:
            total_docs = 0

        total_pages = math.ceil(total_docs / PAGE_SIZE) if total_docs > 0 else 0
        if total_pages > 0 and page > total_pages:
            page = total_pages

        skip = (page - 1) * PAGE_SIZE if total_pages != 0 else 0

        # Build pipeline with pagination
        pipeline = []
        if match_criteria:
            pipeline.append({"$match": match_criteria})
        pipeline.append({"$sort": {"timestamp": -1}})
        if skip:
            pipeline.append({"$skip": skip})
        pipeline.append({"$limit": PAGE_SIZE})

        results = []
        try:
            for doc in collection.aggregate(pipeline):
                results.append(doc)
        except Exception as e:
            # Catch aggregation errors and return a friendly message
            print(f"Aggregation error: {e}")
            client.close()
            return render_template(
                'index.html',
                results=[],
                error=f"Search failed: {e}",
                app=app_val,
                host=host_val,
                env=env_val,
                level=level_val,
                start=start_time_str,
                end=end_time_str,
                page=page,
                total=total_docs,
                total_pages=total_pages,
                page_size=PAGE_SIZE,
                has_prev=(page > 1 and total_pages > 0),
                has_next=(total_pages > 0 and page < total_pages),
                prev_page=(page - 1) if (page > 1 and total_pages > 0) else None,
                next_page=(page + 1) if (total_pages > 0 and page < total_pages) else None,
            )

        client.close()
        return render_template(
            'index.html',
            results=results,
            error="",
            app=app_val,
            host=host_val,
            env=env_val,
            level=level_val,
            start=start_time_str,
            end=end_time_str,
            page=page,
            total=total_docs,
            total_pages=total_pages,
            page_size=PAGE_SIZE,
            has_prev=(page > 1 and total_pages > 0),
            has_next=(total_pages > 0 and page < total_pages),
            prev_page=(page - 1) if (page > 1 and total_pages > 0) else None,
            next_page=(page + 1) if (total_pages > 0 and page < total_pages) else None,
        )

    return app