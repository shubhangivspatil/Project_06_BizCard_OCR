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
import pandas as pd

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

    @staticmethod
    def update_card_details(card_id, updated_details):
        session = SessionLocal()
        try:
            card = session.query(BusinessCard).filter_by(id=card_id).first()
            if card:
                logger.debug(f"Updating card with ID: {card_id}")
                for key, value in updated_details.items():
                    logger.debug(f"Updating field '{key}' with value: {value}")
                    setattr(card, key, value)
                session.commit()
                logger.debug("Card details updated successfully.")
            else:
                logger.warning(f"Card with ID {card_id} not found.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating card details: {e}")
        finally:
            session.close()

# Function to retrieve all business cards from the database
def get_all_business_cards():
    session = SessionLocal()
    try:
        # Retrieve all business cards
        cards = session.query(BusinessCard).all()
        # Convert to a DataFrame for easier display
        card_data = [{
            "ID": card.id,
            "Company Name": card.company_name,
            "Card Holder": card.card_holder,
            "Designation": card.designation,
            "Mobile Number": card.mobile_number,
            "Email": card.email,
            "Website": card.website,
            "Area": card.area,
            "City": card.city,
            "State": card.state,
            "Pin Code": card.pin_code
        } for card in cards]
        return pd.DataFrame(card_data)
    except Exception as e:
        logger.error(f"Error retrieving business cards: {e}")
        return pd.DataFrame()  # Return an empty DataFrame on error
    finally:
        session.close()

# Streamlit UI
st.title("BizCardX: Extracting Business Card Data with OCR")
st.markdown("""
**Technologies:**
- OCR
- Streamlit GUI
- SQL

**Project Overview**

BizCardX is a Streamlit application designed to extract and manage information from business cards using easyOCR. Users can upload images of business cards, extract relevant details, and store the information in a database. The application also allows viewing, updating, and deleting data through an intuitive GUI.

**Creator:**
- Shubhangi Patil

**Project:**
- Data Science

**GitHub Link:**
- [GitHub Repository](https://github.com/shubhangivspatil)
""")

uploaded_file = st.file_uploader("Choose a business card image to upload", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    card_details = BusinessCardProcessor.extract_and_process_image(uploaded_file)

    if card_details:
        st.write("Processed card details:")
        st.json(card_details)
        st.image(uploaded_file, caption='Uploaded Image with OCR bounding boxes', use_column_width=True)

        # Retrieve the latest card ID (or use a different method to get card ID)
        session = SessionLocal()
        last_card = session.query(BusinessCard).order_by(BusinessCard.id.desc()).first()
        if last_card:
            card_id = last_card.id

            st.write("Update Business Card Details")
            with st.form(key="update_card_form"):
                updated_card_holder = st.text_input("Card Holder", value=card_details['card_holder'][0] if card_details['card_holder'] else "")
                updated_designation = st.text_input("Designation", value=card_details['designation'][0] if card_details['designation'] else "")
                updated_mobile_number = st.text_input("Mobile Number", value=card_details['mobile_number'][0] if card_details['mobile_number'] else "")
                updated_email = st.text_input("Email", value=card_details['email'][0] if card_details['email'] else "")
                updated_website = st.text_input("Website", value=card_details['website'][0] if card_details['website'] else "")
                updated_area = st.text_input("Area", value=card_details['area'][0] if card_details['area'] else "")
                updated_city = st.text_input("City", value=card_details['city'][0] if card_details['city'] else "")
                updated_state = st.text_input("State", value=card_details['state'][0] if card_details['state'] else "")
                updated_pin_code = st.text_input("Pin Code", value=card_details['pin_code'][0] if card_details['pin_code'] else "")

                submit_button = st.form_submit_button(label="Update Card Details")

            if submit_button:
                logger.debug("Form submitted. Updating card details in the database.")
                updated_details = {
                    'card_holder': updated_card_holder,
                    'designation': updated_designation,
                    'mobile_number': updated_mobile_number,
                    'email': updated_email,
                    'website': updated_website,
                    'area': updated_area,
                    'city': updated_city,
                    'state': updated_state,
                    'pin_code': updated_pin_code
                }

                BusinessCardProcessor.update_card_details(card_id, updated_details)
                st.success("Card details updated successfully.")
        else:
            st.write("No card found to update.")
    else:
        st.write("No data extracted from the uploaded image.")

# Additional button to show database table
if st.button("Show Database Table"):
    logger.debug("Fetching business cards from the database.")
    business_cards_df = get_all_business_cards()
    if not business_cards_df.empty:
        st.write("Business Cards Database:")
        st.dataframe(business_cards_df)
    else:
        st.write("No business cards found in the database.")
