import React, { useState } from "react";
import axios from "axios";

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [confidence, setConfidence] = useState(0.75);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFileSelect = (file) => {
    if (file && file.type.startsWith("image/")) {
      setSelectedFile(file);
      setError(null);
      setResults(null);
    } else {
      setError("Please select a valid image file");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const uploadImage = async () => {
    if (!selectedFile) {
      setError("Please select an image first");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("image", selectedFile);
    formData.append("confidence", confidence.toString());

    try {
      const response = await axios.post("/api/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 30000, // 30 second timeout
      });

      setResults(response.data);
    } catch (err) {
      console.error("Upload error:", err);
      setError(
        err.response?.data?.error ||
          "An error occurred while processing the image"
      );
    } finally {
      setLoading(false);
    }
  };

  // const downloadImage = async (filename) => {
  //   try {
  //     const response = await axios.get(`/api/download/${filename}`, {
  //       responseType: "blob",
  //     });

  //     const url = window.URL.createObjectURL(new Blob([response.data]));
  //     const link = document.createElement("a");
  //     link.href = url;
  //     link.setAttribute("download", filename);
  //     document.body.appendChild(link);
  //     link.click();
  //     link.remove();
  //     window.URL.revokeObjectURL(url);
  //   } catch {
  //     setError("Failed to download image");
  //   }
  // };

  const clearResults = () => {
    setResults(null);
    setSelectedFile(null);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Quadrat Detection & Rectification Tool
          </h1>
          <p className="text-lg text-gray-600">
            Upload underwater images to detect and rectify tilted quadrats
          </p>
        </div>

        {/* Upload Section */}
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
            <h2 className="text-xl font-semibold mb-4">Upload Image</h2>

            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragOver
                  ? "border-blue-400 bg-blue-50"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <div className="space-y-4">
                <div className="text-6xl text-gray-400">‧₊˚ ☁️⋅📷𓂃 ࣪ ִֶָ☾.</div>
                <div>
                  <p className="text-lg font-medium text-gray-900">
                    Drop your image here or click to browse
                  </p>
                  <p className="text-sm text-gray-500">
                    Supports JPG, PNG, and other image formats
                  </p>
                </div>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => handleFileSelect(e.target.files[0])}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="inline-block px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 cursor-pointer transition-colors"
                >
                  Browse Files
                </label>
              </div>
            </div>

            {/* Selected File Info */}
            {selectedFile && (
              <div className="mt-4 p-4 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-600">
                  Selected:{" "}
                  <span className="font-medium">{selectedFile.name}</span>(
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                </p>
              </div>
            )}

            {/* Confidence Slider */}
            <div className="mt-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Confidence Threshold: {confidence}
              </label>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={confidence}
                onChange={(e) => setConfidence(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0.1 (Less strict)</span>
                <span>0.9 (More strict)</span>
              </div>
            </div>

            {/* Process Button */}
            <div className="mt-6 flex gap-4">
              <button
                onClick={uploadImage}
                disabled={!selectedFile || loading}
                className="flex-1 px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {loading ? (
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                    Processing...
                  </div>
                ) : (
                  "Detect & Rectify Quadrats"
                )}
              </button>

              {results && (
                <button
                  onClick={clearResults}
                  className="px-6 py-3 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors font-medium"
                >
                  Clear Results
                </button>
              )}
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
              <p className="font-medium">Error:</p>
              <p>{error}</p>
            </div>
          )}

          {/* Results Section */}
          {results && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h2 className="text-xl font-semibold mb-4">
                  Detection Results
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-600">
                      {results.total_detected}
                    </div>
                    <div className="text-sm text-gray-600">Quadrats Found</div>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">
                      {results.confidence_threshold}
                    </div>
                    <div className="text-sm text-gray-600">Confidence Used</div>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-purple-600">
                      {results.rectified_quadrats.length}
                    </div>
                    <div className="text-sm text-gray-600">
                      Successfully Rectified
                    </div>
                  </div>
                </div>
              </div>

              {/* Original and Annotated Images */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold mb-4">
                  Detection Visualization
                </h3>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-medium mb-2">Original Image</h4>
                    <img
                      src={`data:image/png;base64,${results.original_image}`}
                      alt="Original"
                      className="w-full rounded-lg border"
                    />
                  </div>

                  <div>
                    <h4 className="font-medium mb-2">
                      Cropped Quadrat Preview
                    </h4>

                    <img
                      src={
                        results.rectified_quadrats?.length > 0
                          ? `data:image/png;base64,${results.rectified_quadrats[0].image_base64}`
                          : `data:image/png;base64,${results.annotated_image}`
                      }
                      alt="Cropped Quadrat Preview"
                      className="w-[40.5vh] rounded-lg border"
                    />

                    {results.rectified_quadrats?.length > 0 && (
                      <p className="text-sm text-gray-600 mt-1">
                        Previewing Quadrat #{results.rectified_quadrats[0].id} (
                        {(
                          results.rectified_quadrats[0].confidence * 100
                        ).toFixed(1)}
                        %)
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Rectified Quadrats */}
              {results.rectified_quadrats.length > 0 && (
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-lg font-semibold mb-4">
                    Cropped Quadrat
                  </h3>

                  <div className="space-y-8">
                    {results.rectified_quadrats.map((quadrat) => (
                      <div
                        key={quadrat.id}
                        className="border-2 border-gray-200 rounded-lg p-6 bg-gray-50"
                      >
                        {/* Quadrat Header */}
                        <div className="flex justify-between items-start mb-4">
                          <h4 className="text-xl font-semibold text-gray-800">
                            Quadrat #{quadrat.id}
                          </h4>
                          <div className="flex gap-2">
                            <span className="px-3 py-1 bg-green-100 text-green-800 text-sm rounded-full">
                              {(quadrat.confidence * 100).toFixed(1)}%
                              confidence
                            </span>
                            <span className="px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full">
                              {quadrat.method_used.replace("_", " ")}
                            </span>
                          </div>
                        </div>

                        {/* Images Grid */}
                        <div className="flex flex-col md:flex-row gap-6">
                          {/* Rectified Quadrat */}
                          <div>
                            <h5 className="font-medium mb-2 text-gray-700">
                              Cropped Quadrat
                            </h5>
                            <img
                              src={`data:image/png;base64,${quadrat.image_base64}`}
                              alt={`Rectified Quadrat ${quadrat.id}`}
                              className="w-full h-[75vh] object-cover rounded-lg border"
                            />
                            <p className="text-sm text-gray-600 mt-1">
                              Size: {quadrat.size.width}×{quadrat.size.height}px
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Detected quadrats moved to bottom */}
                  <div className="mt-8">
                    <h4 className="font-medium mb-2">Detected Quadrats</h4>
                    <img
                      src={`data:image/png;base64,${results.annotated_image}`}
                      alt="Annotated"
                      className="w-full rounded-lg border"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
