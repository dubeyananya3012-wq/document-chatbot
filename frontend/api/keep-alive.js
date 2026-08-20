export default async function handler(request, response) {
  // Read target backend API from environment variables, fallback to local default
  const backendBaseUrl = process.env.API_BASE_URL || 'http://localhost:8000';
  const healthUrl = `${backendBaseUrl.replace(/\/$/, '')}/health`;

  try {
    const res = await fetch(healthUrl);
    
    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    const data = await res.json();
    return response.status(200).json({
      success: true,
      message: `Successfully pinged backend health endpoint: ${healthUrl}`,
      data
    });
  } catch (error) {
    return response.status(500).json({
      success: false,
      message: `Failed to ping backend at ${healthUrl}`,
      error: error.message
    });
  }
}
