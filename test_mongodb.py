from personalization_layer.mongodb import test_connection, db

if test_connection():
    print("MongoDB Atlas connection successful!")
    print("Database:", db.name)
    print("Collections:", db.list_collection_names())
else:
    print("MongoDB Atlas connection failed!")