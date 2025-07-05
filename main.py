from fastapi import FastAPI, HTTPException
import httpx
from bs4 import BeautifulSoup
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

    # Check for invalid tracking number
    if "The Postal Service could not locate the tracking information" in html:
        raise HTTPException(status_code=404, detail="Tracking number not found or invalid")

    soup = BeautifulSoup(html, 'html.parser')

    tracking_data = {}

    # Extracting tracking number
    tracking_number_span = soup.find('span', class_='tracking-number')
    tracking_data['tracking_number'] = tracking_number_span.text.strip() if tracking_number_span else None

    # Extracting delivery information (status, ETA, etc.)
    banner_div = soup.find('div', class_='latest-update-banner-wrapper')
    if banner_div:
        delivery_info = {}
        header = banner_div.find('h3')
        if header:
            delivery_info['status_title'] = header.text.strip().replace(':', '')

        eta_wrap = banner_div.find('span', class_='eta_wrap')
        if eta_wrap:
            day = eta_wrap.find('em', class_='day')
            date = eta_wrap.find('strong', class_='date')
            month_year = eta_wrap.find('span', class_='month_year')
            time_val = eta_wrap.find('strong', class_='time')

            delivery_info['day'] = day.text.strip() if day else None
            delivery_info['date'] = date.text.strip() if date else None
            delivery_info['month_year'] = ' '.join(month_year.text.split()) if month_year else None
            delivery_info['time'] = re.sub(r'\s+', ' ', time_val.text).strip() if time_val else None
        
        banner_content = banner_div.find('p', class_='banner-content')
        delivery_info['detailed_status'] = banner_content.text.strip() if banner_content else None
        tracking_data['expected_delivery'] = delivery_info
    else:
        tracking_data['expected_delivery'] = None

    # Extracting tracking history
    tracking_history = []
    progress_bar_container = soup.find('div', class_='tracking-progress-bar-status-container')
    if progress_bar_container:
        steps = progress_bar_container.find_all('div', class_='tb-step')
        for step in steps:
            if 'toggle-history-container' in step.get('class', []):
                continue
            
            history_item = {}
            status_detail_p = step.find('p', class_='tb-status-detail')
            if not status_detail_p:
                status_detail_p = step.find('p', class_='tb-status')

            location_p = step.find('p', class_='tb-location')
            date_time_p = step.find('p', class_='tb-date')
            
            if status_detail_p:
                history_item['status'] = status_detail_p.text.strip()
            else:
                continue

            history_item['location'] = ' '.join(location_p.text.split()) if location_p else None
            history_item['datetime'] = ' '.join(date_time_p.text.split()) if date_time_p else None
            
            tracking_history.append(history_item)

    tracking_data['tracking_history'] = tracking_history

    return tracking_data
