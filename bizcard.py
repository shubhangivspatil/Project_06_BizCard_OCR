import streamlit as st
import easyocr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from PIL import Image, ImageDraw
import numpy as np
import re
import logging
import os

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine("postgresql://postgres:admin@localhost:5432/bizcard_db", echo=True)
Base = declarative_base()
SessionLocal = scoped_session(sessionmaker(bind=engine))

class BusinessCard(Base):
    __tablename__ = 'business_cards'
    id = Column(Integer, primary_key=True)
    company_name = Column(String)
    card_holder = Column(String)
    designation = Column(String)
    mobile_number = Column(String)
    email = Column(String)
    website = Column(String)
    area = Column(String)
    city = Column(String)
    state = Column(String)
    pin_code = Column(String)

Base.metadata.create_all(engine)

# OCR setup
reader = easyocr.Reader(['en'])

class BusinessCardProcessor:
    @staticmethod
    @st.cache_data
    def extract_and_process_image(image_data):
        logger.debug("Opening image.")
        try:
            image = Image.open(image_data)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            logger.debug(f"Image mode after conversion: {image.mode}")

            image_np = np.array(image)
            logger.debug("Image converted to numpy array.")

            results = reader.readtext(image_np, detail=1)
            logger.debug(f"OCR results: {results}")
        except Exception as e:
            logger.error(f"Error during OCR process: {e}")
            return None

        card_details = {
            "company_name": [],
            "card_holder": [],
            "designation": [],
            "mobile_number": [],
            "email": [],
            "website": [],
            "area": [],
            "city": [],
            "state": [],
            "pin_code": []
        }

        try:
            for i, (bbox, text, prob) in enumerate(results):
                logger.debug(f"OCR Result - Text: {text}, Probability: {prob}")
                text_lower = text.lower()
                text_cleaned = re.sub(r'[ -]', '', text_lower)

                if i == 0:
                    card_details["card_holder"].append(text)
                elif i == 1:
                    card_details["designation"].append(text)

                if "@" in text_lower and "." in text_lower and "email" not in text_lower:
                    card_details['email'].append(text)
                elif any(ext in text_lower for ext in ["www", "http", ".com", ".net", ".org"]):
                    card_details['website'].append(text)
                elif 'tamilnadu' in text_lower or 'tamil nadu' in text_lower:
                    card_details['state'].append("Tamil Nadu")
                    cleaned_pin_code = text.replace("TamilNadu ", "").replace("Tamil Nadu ", "").strip()
                    if cleaned_pin_code.isdigit():
                        card_details['pin_code'].append(cleaned_pin_code)
                elif text.isdigit() and (len(text) == 6):
                    card_details['pin_code'].append(text)
                elif re.match(r'\+?\d[\d\s\-()]{8,}', text):
                    card_details['mobile_number'].append(text)
                elif "area" in text_lower or "sector" in text_lower:
                    card_details['area'].append(text)
                elif "city" in text_lower or "town" in text_lower:
                    card_details['city'].append(text)

            # Draw bounding boxes
            draw = ImageDraw.Draw(image)
            for bbox in [bbox for bbox, _, _ in results]:
                top_left, bottom_right = tuple(bbox[0]), tuple(bbox[2])
                draw.rectangle([top_left, bottom_right], outline='red')

            debug_image_path = "debug_image_with_bboxes.jpg"
            debug_images_dir = 'debug_images'
            os.makedirs(debug_images_dir, exist_ok=True)
            debug_full_path = os.path.join(debug_images_dir, debug_image_path)
            image.save(debug_full_path, 'JPEG')
            logger.debug(f"Image saved at {debug_full_path}")

            new_card = BusinessCard(**{key: "; ".join(value) for key, value in card_details.items()})
            SessionLocal.add(new_card)
            SessionLocal.commit()
            logger.debug("Card details saved successfully.")
        except Exception as e:
            SessionLocal.rollback()
            logger.error(f"Failed to save card details: {e}")
            return None

        return card_details

# Streamlit 
st.title("BizCardX: Extracting Business Card Data with OCR")
st.markdown("""
**Technologies:**
- OCR
- Streamlit GUI
- SQL
- Data Extraction
""")

uploaded_file = st.file_uploader("Choose a business card image to upload", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    card_details = BusinessCardProcessor.extract_and_process_image(uploaded_file)
    if card_details:
        st.write("Processed card details:")
        st.json(card_details)
        st.image(uploaded_file, caption='Uploaded Image with OCR bounding boxes', use_column_width=True)
    else:
        st.write("No data extracted from the uploaded image.")
