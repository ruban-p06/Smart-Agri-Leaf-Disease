import os
from flask import Flask, redirect, render_template, request, url_for
import requests
from io import BytesIO
from PIL import Image
import torchvision.transforms.functional as TF
import CNN
import numpy as np
import torch
import pandas as pd
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

gemini_model = genai.GenerativeModel("models/gemini-2.0-flash")


# CONFIGURATION
# Replace with your actual IP addresses
ESP32_IP = "10.100.201.238" 
CAM_IP = "192.168.137.228"

disease_info = pd.read_csv('disease_info.csv' , encoding='cp1252')
supplement_info = pd.read_csv('supplement_info.csv',encoding='cp1252')

model = CNN.CNN(39)    
model.load_state_dict(torch.load("plant_disease_model_1_latest.pt"))
model.eval()

def prediction(image_path):
    image = Image.open(image_path)
    image = image.resize((224, 224))
    input_data = TF.to_tensor(image)
    input_data = input_data.view((-1, 3, 224, 224))
    output = model(input_data)
    output = output.detach().numpy()
    index = np.argmax(output)
    return index

def gemini_early_prediction(image_path):
    image = Image.open(image_path)

    prompt = """
    You are an agricultural plant disease expert.
    Analyze the given plant leaf image and predict:
    1. Possible early-stage disease (even if symptoms are mild)
    2. Visible early symptoms
    3. Risk level (Low / Medium / High)
    4. Preventive actions to avoid severe disease
    5. Whether immediate treatment is required

    Respond in simple bullet points.
    """

    response = gemini_model.generate_content(
        [prompt, image],
        generation_config={
            "temperature": 0.4,
            "max_output_tokens": 400
        }
    )

    return response.text


app = Flask(__name__)

@app.route('/')
def home_page():
    # Default Simulated Data
    sensors = {
        'soil_moisture': 65,
        'water_level': 80,
        'temperature': 24,
        'pump_status': 'OFF',
        'solenoid_status': 'OFF',
        'mq3':120
    }
    
    # Try fetching real data
    try:
        response = requests.get(f"http://{ESP32_IP}/data", timeout=2)
        if response.status_code == 200:
            data = response.json()
            # Update sensors with real data
            sensors.update(data)
    except Exception as e:
        print(f"Error connecting to ESP32: {e}")

    return render_template('dashboard.html', sensors=sensors, cam_ip=CAM_IP)

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    sensors = {
        'soil_moisture': 65,
        'water_level': 80,
        'temperature': 24
    }
    if request.method == 'POST':
        image = request.files['image']
        filename = image.filename
        file_path = os.path.join('static/uploads', filename)
        image.save(file_path)
        print(file_path)
        pred = prediction(file_path)
        title = disease_info['disease_name'][pred]
        description =disease_info['description'][pred]
        prevent = disease_info['Possible Steps'][pred]
        image_url = disease_info['image_url'][pred]
        supplement_name = supplement_info['supplement name'][pred]
        supplement_image_url = supplement_info['supplement image'][pred]
        supplement_buy_link = supplement_info['buy link'][pred]
        
        # Pass specifically 'uploads/filename' so url_for('static', filename=...) works cleanly in template if needed
        # Or just pass the relative path derived for display
        display_image_path = 'uploads/' + filename
        
        return render_template('dashboard.html', 
                               title=title, 
                               desc=description, 
                               prevent=prevent, 
                               image_url=image_url, 
                               pred=pred, 
                               sname=supplement_name, 
                               simage=supplement_image_url, 
                               buy_link=supplement_buy_link,
                               sensors=sensors,
                               uploaded_image=display_image_path,
                               cam_ip=CAM_IP)
    return redirect('/')

@app.route('/analyze_feed', methods=['POST'])
def analyze_feed():
    try:
        # Assuming the camera provides a snapshot at this URL
        # Using /cam-hi.jpg based on camera.ino
        snapshot_url = request.form.get('snapshot_url', f"http://{CAM_IP}/cam-hi.jpg")
        
        response = requests.get(snapshot_url, timeout=5)
        if response.status_code == 200:
            image_data = BytesIO(response.content)
            image = Image.open(image_data)
            
            # Save strictly for display purposes if needed, or just process in memory
            # Saving to static to match existing logic
            filename = "live_snapshot.jpg"
            file_path = os.path.join('static/uploads', filename)
            image.save(file_path)
            
            # Run existing prediction logic
            pred = prediction(file_path)
            title = disease_info['disease_name'][pred]
            description = disease_info['description'][pred]
            prevent = disease_info['Possible Steps'][pred]
            image_url = disease_info['image_url'][pred]
            supplement_name = supplement_info['supplement name'][pred]
            supplement_image_url = supplement_info['supplement image'][pred]
            supplement_buy_link = supplement_info['buy link'][pred]
            
            # Get current sensor data again to keep context
            sensors = {
                'soil_moisture': 65, 'water_level': 80, 'temperature': 24, 
                'pump_status': 'OFF', 'solenoid_status': 'OFF'
            }
            try:
                r = requests.get(f"http://{ESP32_IP}/data", timeout=2)
                if r.status_code == 200: sensors.update(r.json())
            except: pass

            display_image_path = 'uploads/' + filename
            
            return render_template('dashboard.html', 
                                   title=title, 
                                   desc=description, 
                                   prevent=prevent, 
                                   image_url=image_url, 
                                   pred=pred, 
                                   sname=supplement_name, 
                                   simage=supplement_image_url, 
                                   buy_link=supplement_buy_link,
                                   sensors=sensors,
                                   uploaded_image=display_image_path,
                                   cam_ip=CAM_IP)
        else:
            return "Failed to capture image from camera", 400
    except Exception as e:
        return f"Error analyzing feed: {e}", 500

@app.route('/early_prediction', methods=['POST'])
def early_prediction():

    if request.method == 'POST':

        # Get uploaded image (same style as submit)
        image = request.files['image']
        filename = "early_" + image.filename
        file_path = os.path.join('static/uploads', filename)
        image.save(file_path)

        print(file_path)

        # Gemini early-stage disease prediction
        early_report = gemini_early_prediction(file_path)

        # Get sensor data
        sensors = {
            'soil_moisture': 65,
            'water_level': 80,
            'temperature': 24,
            'pump_status': 'OFF',
            'solenoid_status': 'OFF',
            'mq3':120
        }

        try:
            response = requests.get(f"http://{ESP32_IP}/data", timeout=2)
            if response.status_code == 200:
                sensors.update(response.json())
        except:
            pass

        return render_template(
            'dashboard.html',
            early_report=early_report,
            sensors=sensors,
            uploaded_image='uploads/' + filename,
            cam_ip=CAM_IP
        )

if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0")
