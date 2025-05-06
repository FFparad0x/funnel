from setuptools import setup, find_packages

setup(
    name="funnelbot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot",
        "openai",
        "python-dotenv",
        "pyyaml",
        "fastapi",
        "uvicorn",
        "requests",
    ],
) 