from app import create_app

site = create_app()

if __name__ == "__main__":
    site.run(host=site.config['APP_HOST'], port=site.config['APP_PORT'], debug=site.config['DEBUG'], load_dotenv=False)
