import axios from 'axios';

// Backend URL
const API_BASE_URL = 'http://127.0.0.1:8001';

export const getForecast = async (lat: number, lon: number) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/v1/forecast`, {
      latitude: lat,
      longitude: lon
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching forecast:", error);
    return null;
  }
};

export const getGridAnalysis = async (points: {lat: number, lon: number}[]) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/v1/grid-analysis`, {
      points: points
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching grid analysis:", error);
    return null;
  }
};
