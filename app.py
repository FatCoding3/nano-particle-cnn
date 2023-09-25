import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

from copy import deepcopy

import matplotlib as mpl
mpl.use("agg")

from matplotlib.backends.backend_agg import RendererAgg
_lock = RendererAgg.lock

from keras.models import Model, load_model
from sklearn.preprocessing import MinMaxScaler,StandardScaler
import joblib


# -- Set side bar
apptitle = 'Nano composite distribution'

st.set_page_config(page_title=apptitle, page_icon=":eyeglasses:")
st.markdown("""
<style>
    * {
       overflow-anchor: none !important;
       }
</style>""", unsafe_allow_html=True)

st.sidebar.markdown("## Select input")

P_NP_interaction = st.sidebar.slider('Interaction between P and NP', 0.4, 0.8, step=0.05, )
NP_NP_interaction = st.sidebar.slider('Interaction between two NP', 0.4, 0.8, step=0.05)
P_ChainLength = st.sidebar.slider('Polymer chain length', 30, 40, step=1)
P_Density = st.sidebar.slider('Polymer density', 1.0, 2.0, step=0.5)*1e-3
NP_Size = st.sidebar.slider('Nano particle size', 3.0, 5.0, step=0.1)

@st.cache_resource
def this_load_model():
  AE = load_model("AE.h5")
  get_encoded= Model(inputs=AE.input, outputs=AE.get_layer("CODE").output)
  get_decoded= Model(inputs=AE.get_layer("DECODE").input, outputs=AE.get_layer("OUTPUT").output)
  RF = joblib.load("RF.joblib")
  return {
    'encoded': get_encoded,
    'decoded': get_decoded,
    'RF': RF
  }

@st.cache_resource
def this_load_scaler():
  scaler_x = joblib.load('scaler/scaler-x.joblib')
  scaler2_x = joblib.load('scaler/scaler2-x.joblib')
  scaler_y = joblib.load('scaler/scaler-y.joblib')
  scaler2_y = joblib.load('scaler/scaler2-y.joblib')
  return scaler_x, scaler2_x, scaler_y, scaler2_y

@st.cache_resource
def get_image(path: str):
  image = Image.open(path)
  return image

model = this_load_model()
scaler_x, scaler2_x, scaler_y, scaler2_y = this_load_scaler()

def normalized_data_from_image(image_array_data):
  x_list = []
  y_list = []

  height = len(image_array_data)
  width = len(image_array_data[0])

  for column in range(width):
    this_y = 0
    this_count = 0
    for row in range(height):
      if image_array_data[row][column] > 20:
        this_count += 1
        this_y += row/height

    if (this_count == 0): continue
    x_list.append(column/width)
    y_list.append(1 - this_y/this_count)

  return np.asarray(x_list), np.asarray(y_list)

def get_predict_graph(image_array_data):
  image_x, image_y = normalized_data_from_image(image_array_data)

  normalize_consts_x =  [77.98153846153846, -5.612307692307695]
  normalize_consts_y =[117.32283619453445, -29.53643790351991]

  un_image_x = image_x * normalize_consts_x[0] + normalize_consts_x[1]
  un_image_y = image_y * normalize_consts_y[0] + normalize_consts_y[1]

  return pd.DataFrame({
    'r': un_image_x*10/64,
    'log_g': un_image_y*5/64 - 3
  })

def predict():
  dataFrame_x = [
    [P_NP_interaction, NP_NP_interaction, P_ChainLength, P_Density, NP_Size]
  ]

  dataFrame_x = scaler_x.transform(dataFrame_x)
  dataFrame_x = scaler2_x.transform(dataFrame_x)

  RF_prediction = model['RF'].predict(dataFrame_x)
  RF_prediction = scaler2_y.inverse_transform(RF_prediction)
  RF_prediction = scaler_y.inverse_transform(RF_prediction)
  RF_prediction.resize(1,1,1,8)

  predicted_rdf = np.asarray(model['decoded'].predict(RF_prediction))
  predicted_rdf.resize(1,64,64)
  predicted_rdf = predicted_rdf[0]*255

  return predicted_rdf

@st.cache_data
def gen_new_data(summit: bool):
  predicted_rdf = predict()
  data = get_predict_graph(predicted_rdf)
  return data

def save_cache():
  st.cache_data.clear()
  gen_new_data(False)

summit = st.sidebar.button('Generate', on_click=save_cache)

st.title('NanoNet: predicting nanoparticles distribution in a polymer matrix')

st.write('The NanoNet is built using a CNN autoencoder and an RF regressor. We use 128 RDFs to build these two components of the nanoNET. The performance of the nanoNET is tested for 32 RDFs that are not used for model building. These 160 RDFs are calculated for a selected range of compositional parameters that yield a large variety of NP distributions in a polymer matrix.')

st.subheader('Description')

st.write('Polymer nanocomposites (PNC) offer a broad range of properties that are intricately connected to the spatial distribution of nanoparticles (NPs) in polymer matrices. Understanding and controlling the distribution of NPs in a polymer matrix is a significantly challenging task')

st.image(get_image('description.png'), caption='Predict by CNN')

st.write('CNN appears to be more efficient for RDF feature extraction in the current problem. A CNN is capable of hierarchical feature learning. It typically consists of multiple layers with increasing levels of abstraction. Outer layers capture low-level features, including edges and textures, while deeper layers learn more complex and abstract representations.')

st.subheader('Generated graph')

st.write('Graph below is generated by our model, you can modify inputs in the side bar.')
st.write(' ')

st.line_chart(gen_new_data(summit), x='r', y='log_g')
