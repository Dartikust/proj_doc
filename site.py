from app import create_app

site = create_app()

if __name__ == "__main__":
    site.run(host='127.0.0.1', port=5000)
