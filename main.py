from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


def main():
    # with initialize(config_path="config/hydra"):
    #     cfg = compose(config_name="config.yaml", return_hydra_config=True)
    #     print(f"Working directory : {os.getcwd()}")
    #     print(cfg)
    # uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    # while (question := input("Enter a question: ")) not in ["exit", "quit", "q"]:
    #     print(question)
    pass


if __name__ == "__main__":
    main()
