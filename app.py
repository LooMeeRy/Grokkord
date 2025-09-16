from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, NoSuchElementException, TimeoutException
import time
import os
import platform
import re

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here' # ตั้งค่า Secret Key สำหรับ Session

LOGIN_URL = "http://alumni.npru.ac.th/activity/index.php"
ACTIVITY_URL = "http://alumni.npru.ac.th/activity/std_card.php"
HISTORY_URL = "http://alumni.npru.ac.th/activity/std_history.php"

def get_geckodriver_path():
    """
    Checks the operating system and returns the correct path for the geckodriver executable.
    """
    system = platform.system()
    if system == 'Windows':
        driver_name = 'geckodriver.exe'
    else:
        driver_name = 'geckodriver'

    return os.path.join(os.path.dirname(__file__), driver_name)

def get_firefox_driver(headless=True):
    """
    Initializes and returns a Firefox WebDriver instance.
    """
    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")

    geckodriver_path = get_geckodriver_path()
    if not os.path.exists(geckodriver_path):
        raise FileNotFoundError(f"Geckodriver not found at: {geckodriver_path}")

    service = Service(geckodriver_path)
    return webdriver.Firefox(service=service, options=options)

def verify_login(username, password):
    """
    Verifies user login credentials by simulating a login on the website.
    """
    driver = None
    try:
        driver = get_firefox_driver(headless=True)
        driver.get(LOGIN_URL)
        driver.find_element(By.ID, "account").send_keys(username)
        driver.find_element(By.ID, "password").send_keys(password)
        driver.find_element(By.ID, "Login").click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "ออกจากระบบ"))
        )
        return True
    except (WebDriverException, TimeoutException) as e:
        print(f"Login verification failed: {e}")
        return False
    finally:
        if driver:
            driver.quit()

def parse_history_text(text):
    """
    Parses the raw text content from the history page to extract activity details.
    """
    history_data = []
    # Split the text into individual activity entries
    entries = re.split(r'\s*\d+\.\s*', text.strip())

    # Process each entry, skipping the first element which might be empty
    for entry in entries[1:]:
        if not entry:
            continue

        lines = entry.strip().split('\n')
        if len(lines) < 2:
            continue

        # Extract data from lines
        activity_info = lines[0].strip()
        code_info = lines[1].strip()
        location_info = lines[2].strip()
        date_info = lines[3].strip()

        # Use regex to find all key information
        activity_name = re.search(r'กิจกรรม:\s*(.*?)\s+', activity_info)
        activity_type = re.search(r'ประเภทกิจกรรม:\s*(.*?)\s+', activity_info)
        code = re.search(r'รหัสบาร์โค้ด:\s*(\S+)', code_info)
        location = re.search(r'สถานที่ทำกิจกรรม:\s*(.*?)\s+', location_info)
        date = re.search(r'วันที่เข้าร่วมกิจกรรม:\s*(.*?)\s+', date_info)

        data = {
            'name': activity_name.group(1).strip() if activity_name else 'ไม่ระบุ',
            'type': activity_type.group(1).strip() if activity_type else 'ไม่ระบุ',
            'code': code.group(1).strip() if code else 'ไม่ระบุ',
            'location': location.group(1).strip() if location else 'ไม่ระบุ',
            'date': date.group(1).strip() if date else 'ไม่ระบุ'
        }
        history_data.append(data)

    return history_data

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if verify_login(username, password):
            session['username'] = username
            session['password'] = password
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="รหัสผ่านหรือชื่อผู้ใช้ไม่ถูกต้อง")

    return render_template('login.html')

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    driver = None
    try:
        driver = get_firefox_driver(headless=True)
        driver.get(LOGIN_URL)
        driver.find_element(By.ID, "account").send_keys(session['username'])
        driver.find_element(By.ID, "password").send_keys(session['password'])
        driver.find_element(By.ID, "Login").click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "ออกจากระบบ"))
        )

        driver.get(HISTORY_URL)

        # Wait for the main table to be present
        main_content = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//table"))
        )

        history_text = main_content.text

        history_data = parse_history_text(history_text)

        compulsory_activities = [item for item in history_data if 'บังคับ' in item.get('type', '')]
        supplementary_activities = [item for item in history_data if 'เสริม' in item.get('type', '')]

        return render_template('history.html',
                               compulsory_activities=compulsory_activities,
                               supplementary_activities=supplementary_activities)

    except (WebDriverException, TimeoutException, NoSuchElementException) as e:
        return render_template('history.html', error=f"เกิดข้อผิดพลาดในการดึงข้อมูลประวัติ: {str(e)}", compulsory_activities=[], supplementary_activities=[])
    except Exception as e:
        return render_template('history.html', error=f"เกิดข้อผิดพลาด: {str(e)}", compulsory_activities=[], supplementary_activities=[])
    finally:
        if driver:
            driver.quit()

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('password', None)
    return redirect(url_for('login'))

@app.route('/get_activities', methods=['GET'])
def get_activities():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้ล็อกอิน"})

    driver = None
    try:
        driver = get_firefox_driver(headless=True)
        driver.get(LOGIN_URL)
        driver.find_element(By.ID, "account").send_keys(session['username'])
        driver.find_element(By.ID, "password").send_keys(session['password'])
        driver.find_element(By.ID, "Login").click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "ออกจากระบบ"))
        )

        driver.get(ACTIVITY_URL)

        dropdown_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "act_id"))
        )

        dropdown = Select(dropdown_element)
        options = [{"text": option.text, "value": option.get_attribute("value")} for option in dropdown.options if option.text and option.get_attribute("value")]

        return jsonify({"success": True, "activities": options})

    except (WebDriverException, TimeoutException, NoSuchElementException) as e:
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาดกับเบราว์เซอร์: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if driver:
            driver.quit()

@app.route('/submit', methods=['POST'])
def submit():
    if 'username' not in session:
        return jsonify({"success": False, "message": "ไม่ได้ล็อกอิน"})

    code_string = request.form.get('code')
    activity_value = request.form.get('activity_value')

    if not code_string or not activity_value:
        return jsonify({"success": False, "message": "ไม่พบโค้ดหรือไม่ได้เลือกกิจกรรม"})

    result = fill_form_with_code(code_string, activity_value)
    return jsonify(result)

def fill_form_with_code(code_string, activity_value):
    driver = None
    try:
        driver = get_firefox_driver(headless=False)
        driver.get(LOGIN_URL)
        driver.find_element(By.ID, "account").send_keys(session['username'])
        driver.find_element(By.ID, "password").send_keys(session['password'])
        driver.find_element(By.ID, "Login").click()

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "ออกจากระบบ"))
        )

        driver.get(ACTIVITY_URL)

        dropdown_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "act_id"))
        )

        dropdown = Select(dropdown_element)
        dropdown.select_by_value(activity_value)

        if len(code_string) != 25:
            return {"success": False, "message": "โค้ดที่สแกนได้ไม่ครบ 25 ตัว"}

        part1 = code_string[0:5]
        part2 = code_string[5:10]
        part3 = code_string[10:15]
        part4 = code_string[15:20]
        part5 = code_string[20:25]

        driver.find_element(By.ID, "serial1").send_keys(part1)
        driver.find_element(By.ID, "serial2").send_keys(part2)
        driver.find_element(By.ID, "serial3").send_keys(part3)
        driver.find_element(By.ID, "serial4").send_keys(part4)
        driver.find_element(By.ID, "serial5").send_keys(part5)

        driver.find_element(By.ID, "button").click()
        time.sleep(5)

        return {"success": True, "message": "กรอกโค้ดสำเร็จแล้ว!"}

    except (WebDriverException, TimeoutException, NoSuchElementException) as e:
        return {"success": False, "message": f"เกิดข้อผิดพลาดกับเบราว์เซอร์: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        if driver:
            driver.quit()

if __name__ == '__main__':
    app.run(debug=False)
