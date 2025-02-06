import streamlit as st
import folium
import json
from streamlit_folium import st_folium
from langchain_openai import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import time

# Load OpenAI API key from Streamlit secrets
OPENAI_API_KEY = "[YOUR_API_KEY]"

# Initialize OpenAI model
llm = OpenAI(temperature=0.5, openai_api_key=OPENAI_API_KEY)

def create_map(geojson_data, legend_title="Legend", x_label="Longitude", y_label="Latitude"):
    """Generate a Folium map from GeoJSON data."""
    m = folium.Map(location=[0, 0], zoom_start=2)
    folium.GeoJson(geojson_data, name="GeoJSON Layer").add_to(m)
    
    # Add a legend as a simple HTML block
    legend_html = f'''
    <div style="position: fixed; bottom: 50px; left: 50px; width: 200px;
                background-color: white; padding: 10px; border-radius: 5px;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.5);">
        <h4>{legend_title}</h4>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

def process_command(command, legend_title, x_label, y_label):
    """Use LLM to interpret user commands."""
    template = """
    Given the following map settings:
    Legend Title: {legend_title}
    X-axis Label: {x_label}
    Y-axis Label: {y_label}
    
    Modify them based on this user request: {command}
    Provide only updated values in JSON format like:
    {{"legend_title": "New Title", "x_label": "New X Label", "y_label": "New Y Label"}}
    """
    prompt = PromptTemplate(template=template, input_variables=["command", "legend_title", "x_label", "y_label"])
    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.run({"command": command, "legend_title": legend_title, "x_label": x_label, "y_label": y_label})
    
    return json.loads(response)

# Streamlit UI
st.title("GIS Mapping with AI-Powered Customization")

# File uploader
uploaded_file = st.file_uploader("Upload a GIS JSON file (GeoJSON format)", type=["json"])

# Store map state in session state
if "legend_title" not in st.session_state:
    st.session_state.legend_title = "Legend"
if "x_label" not in st.session_state:
    st.session_state.x_label = "Longitude"
if "y_label" not in st.session_state:
    st.session_state.y_label = "Latitude"

# Process uploaded file
if uploaded_file:
    geojson_data = json.load(uploaded_file)

    # Create map with current session state
    map_obj = create_map(geojson_data, st.session_state.legend_title, st.session_state.x_label, st.session_state.y_label)
    
    # Render map
    st_folium(map_obj, width=700, height=500, key="map")

    # Input for customization command
    user_input = st.text_input("Enter your customization command:")

    if user_input:
        # Get updated values from AI
        updated_values = process_command(user_input, st.session_state.legend_title, st.session_state.x_label, st.session_state.y_label)

        # Update session state
        st.session_state.legend_title = updated_values.get("legend_title", st.session_state.legend_title)
        st.session_state.x_label = updated_values.get("x_label", st.session_state.x_label)
        st.session_state.y_label = updated_values.get("y_label", st.session_state.y_label)

        # Re-render map with updated values
        map_obj = create_map(geojson_data, st.session_state.legend_title, st.session_state.x_label, st.session_state.y_label)
        st_folium(map_obj, width=700, height=500, key="map")
