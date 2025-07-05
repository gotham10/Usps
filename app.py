from flask import Flask, jsonify, Response
import cloudscraper
from bs4 import BeautifulSoup
import json
import re
import os

def scrape_usps_tracking(tracking_number):
    # Use cloudscraper to bypass anti-bot measures
    scraper = cloudscraper.create_scraper()
    
    url = f"https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1={tracking_number}"
    
    try:
        # Make the request using the cloudscraper session
        response = scraper.get(url, timeout=20)
        response.raise_for_status()
    except Exception as e:
        # This will catch connection errors or blocks that cloudscraper can't solve
        return {"error": f"Failed to retrieve data from USPS: {e}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Check if the page returned a "no records found" message
    error_div = soup.find('div', id='error-page')
    if error_div:
        return {"error": "Tracking number not found according to USPS."}

    tracking_data = {}

    tracking_number_span = soup.find('span', class_='tracking-number')
    tracking_data['tracking_number'] = tracking_number_span.text.strip() if tracking_number_span else "Not Found"

    banner_div = soup.find('div', class_='latest-update-banner-wrapper')
    if banner_div:
        delivery_info = {}
        
        for hint in banner_div.find_all('span', class_='hint'):
            hint.decompose()

        header = banner_div.find('h3')
        delivery_info['status_title'] = ' '.join(header.text.split()).replace(':', '') if header else None

        eta_wrap = banner_div.find('span', class_='eta_wrap')
        if eta_wrap:
            day = eta_wrap.find('em', class_='day')
            date = eta_wrap.find('strong', class_='date')
            month_year = eta_wrap.find('span', class_='month_year')
            time_val = eta_wrap.find('strong', class_='time')

            delivery_info['day'] = day.text.strip() if day else None
            delivery_info['date'] = date.text.strip() if date else None
            delivery_info['month_year'] = ' '.join(month_year.text.split()) if month_year else None
            delivery_info['time'] = ' '.join(time_val.text.split()) if time_val else None
        
        banner_content = banner_div.find('p', class_='banner-content')
        delivery_info['detailed_status'] = banner_content.text.strip() if banner_content else None
            
        tracking_data['expected_delivery'] = delivery_info
    else:
        tracking_data['expected_delivery'] = None

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
                history_item['status'] = ' '.join(status_detail_p.text.split())
            else:
                continue

            history_item['location'] = ' '.join(location_p.text.split()) if location_p else None
            history_item['datetime'] = ' '.join(date_time_p.text.split()) if date_time_p else None
            
            tracking_history.append(history_item)

    tracking_data['tracking_history'] = tracking_history

    return tracking_data

app = Flask(__name__)

@app.route('/')
def index():
    usage_html = """
    <h1>USPS Tracking API</h1>
    <p>Usage: Go to <code>/&lt;tracking_number&gt;</code> to get tracking information.</p>
    <p>Example: <a href="/9400150105501041088569">/9400150105501041088569</a></p>
    """
    return usage_html

@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

@app.route('/<string:tracking_number>')
def get_tracking_data(tracking_number):
    if not re.match(r'^[A-Za-z0-9]{10,40}$', tracking_number):
        return jsonify({"error": "Invalid tracking number format."}), 400
        
    data = scrape_usps_tracking(tracking_number)
    
    if "error" in data:
        return jsonify(data), 502
    if not data.get('tracking_history'):
         return jsonify({"error": "Tracking information not found or failed to parse. The parser may need an update or the request was blocked."}), 404

    return jsonify(data)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
