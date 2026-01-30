import streamlit as st
import httpx
from config import settings

API_URL = settings.api_url

st.set_page_config(
    page_title="Federal Reserve Chatbot",
    layout="wide"
)

st.title("Ask Questions About Federal Reserve Reports")

if 'last_request_id' not in st.session_state:
    st.session_state['last_request_id'] = None
if 'last_answer' not in st.session_state:
    st.session_state['last_answer'] = None
if 'last_sources' not in st.session_state:
    st.session_state['last_sources'] = None

question = st.text_input("Enter your question:")

if st.button("Ask"):
    if question:
        with st.spinner("Thinking..."):
            try:
                response = httpx.post(f"{API_URL}/query", json={"question": question}, timeout=300)
                response.raise_for_status()
                result = response.json()

                st.session_state['last_request_id'] = result.get("request_id")
                st.session_state['last_answer'] = result.get("answer", "No answer received.")
                st.session_state['last_sources'] = result.get("retrieved", [])

            except httpx.HTTPStatusError as e:
                st.error(f"API Error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                st.error(f"Connection Error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
    else:
        st.warning("Please enter a question.")

# Display the last answer and sources if available
if st.session_state['last_answer']:
    st.subheader("Answer:")
    st.markdown(st.session_state['last_answer'])

if st.session_state['last_sources']:
    st.subheader("Retrieved Sources:")
    st.json(st.session_state['last_sources'])

if st.session_state['last_request_id']:
    st.header("Rate the last answer")
    rating = st.slider("Score (1 to 5)", 1, 5, 3)
    comment = st.text_area("Comment (optional)")
    
    if st.button("Submit Rating"):
        try:
            payload = {
                "request_id": st.session_state['last_request_id'],
                "rating": rating,
                "comment": comment
            }
            response = httpx.post(f"{API_URL}/rate", json=payload)
            response.raise_for_status()
            st.success("Rating submitted successfully!")
            st.session_state['last_request_id'] = None # Reset after submission
            st.session_state['last_answer'] = None
            st.session_state['last_sources'] = None
        except httpx.HTTPStatusError as e:
            st.error(f"Error submitting rating: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            st.error(f"Connection Error: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred while submitting the rating: {e}")
