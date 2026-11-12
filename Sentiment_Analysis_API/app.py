from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from textblob import TextBlob

app = FastAPI(
    title="Feedback Sentiment API",
    description="Score feedback or review text as POSITIVE, NEGATIVE, or NEUTRAL.",
    version="1.0.0",
)

print("TextBlob ready.")


class TextPayload(BaseModel):
    text: str


class SentimentOut(BaseModel):
    label: str
    confidence: float


class BatchPayload(BaseModel):
    texts: list[str]


def classify_sentiment(text: str) -> dict:
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity

    if polarity > 0:
        label = "POSITIVE"
        confidence = (polarity + 1) / 2
    elif polarity < 0:
        label = "NEGATIVE"
        confidence = abs(polarity)
    else:
        label = "NEUTRAL"
        confidence = 0.5

    return {"label": label, "confidence": round(confidence, 4)}


@app.get("/")
def root():
    return {"status": "ok", "message": "Open /docs to try the API"}


@app.post("/analyze", response_model=SentimentOut)
def analyze(payload: TextPayload):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    return classify_sentiment(payload.text)


@app.post("/analyze_batch")
def analyze_batch(payload: BatchPayload):
    results = []
    for text in payload.texts:
        scored = classify_sentiment(text)
        results.append({"text": text, **scored})
    return {"results": results}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
