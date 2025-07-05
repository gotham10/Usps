from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
import json
import re

def scrape_usps_tracking(tracking_number):
    url = f"https://tools.usps.com/go/TrackConfirmAction?qtc_tLabels1={tracking_number}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'tools.usps.com',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to retrieve data from USPS: {e}"}

    soup = BeautifulSoup(response.content, 'html.parser')
    
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

@app.route('/<string:tracking_number>')
def get_tracking_data(tracking_number):
    if not re.match(r'^[A-Za-z0-9]{10,40}$', tracking_number):
        return jsonify({"error": "Invalid tracking number format."}), 400
        
    data = scrape_usps_tracking(tracking_number)
    
    if "error" in data:
        return jsonify(data), 502
    if not data.get('tracking_history'):
         return jsonify({"error": "Tracking information not found or failed to parse. The USPS site may be blocking the request."}), 404

    return jsonify(data)
if __name__ == '__main__':
    app.run(debug=True, port=5001)
