import requests

SERVER_URL = "http://localhost:3000/execute"

# Scripts to control Puppeteer dynamically
scripts = [
    {"script": "await page.goto('https://www.wuxiabox.com/novel/trxs9227_1.html', { waitUntil: 'networkidle2' });", "commandId": 1},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 2},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 3},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 4},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 5},
    {"script": "await page.waitForSelector('a.next');", "commandId": 6},                
    {"script": "await page.click('a.next');", "commandId": 7},
    {"script": ";", "commandId": 8},
    {"script": "await page.waitForSelector('a.next');", "commandId": 9},    
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 10},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 11},
    {"script": "await page.click('a.next');", "commandId": 12},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 13},
    {"script": "await page.evaluate(() => window.scrollBy(0, 300));", "commandId": 14},
]

for script in scripts:
    response = requests.post(SERVER_URL, json=script)
    if response.status_code == 200:
        screenshot_path = f"screenshot_{script['commandId']}.bmp"
        with open(screenshot_path, "wb") as f:
            f.write(response.content)
        print(f"Screenshot saved: {screenshot_path}")
    else:
        print(f"Error executing script {script['commandId']}: {response.text}")



# await page.evaluate(() => document.body.style.zoom = '130%');