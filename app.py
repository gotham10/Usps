from fastapi import FastAPI, HTTPException
import httpx
import re

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

@app.get("/{tracking_number}")
async def track_usps(tracking_number: str):
    url = f"https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1={tracking_number}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=HEADERS, timeout=20)
            html = response.text
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch tracking info: {e}")

    if "Tracking Number:" not in html:
        raise HTTPException(status_code=404, detail="Tracking number not found or invalid")

    tracking_match = re.search(r'<span class="tracking-number">\s*(.*?)\s*</span>', html)
    tracking_num = tracking_match.group(1) if tracking_match else tracking_number

    status_title = extract_tag_text(html, r'<h3[^>]*>(.*?)</h3>')
    detailed_status = extract_tag_text(html, r'<p class="banner-content">(.*?)</p>')

    day = extract_tag_text(html, r'<em class="day">(.*?)</em>')
    date = extract_tag_text(html, r'<strong class="date">(.*?)</strong>')
    month_year = extract_tag_text(html, r'<span class="month_year">(.*?)</span>')
    time_val = extract_tag_text(html, r'<strong class="time">(.*?)</strong>')

    history_pattern = re.findall(
        r'<div class="tb-step[^"]*">.*?<p class="tb-status(?:-detail)?">(.*?)</p>.*?<p class="tb-location">(.*?)</p>.*?<p class="tb-date">(.*?)</p>',
        html, re.DOTALL
    )

    history = []
    for status, location, dt in history_pattern:
        history.append({
            "status": clean_text(status),
            "location": clean_text(location),
            "datetime": clean_text(dt)
        })

    return {
        "tracking_number": tracking_num,
        "expected_delivery": {
            "status_title": clean_text(status_title),
            "detailed_status": clean_text(detailed_status),
            "day": clean_text(day),
            "date": clean_text(date),
            "month_year": clean_text(month_year),
            "time": clean_text(time_val)
        },
        "tracking_history": history
    }

def extract_tag_text(html, pattern):
    match = re.search(pattern, html, re.DOTALL)
    return clean_text(match.group(1)) if match else None

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip() if text else None
