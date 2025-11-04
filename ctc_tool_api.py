"""
CTC Budget Checker Tool API
Simple Flask endpoint to check if candidate's expected CTC is within budget
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for Ultravox to call this endpoint

@app.route('/check-ctc', methods=['POST'])
def check_ctc():
    """
    Check if expected CTC is within budget range

    Expected JSON body:
    {
        "expected_ctc": "45",  # User's expected CTC in LPA
        "max_budget": "40"     # Maximum budget in LPA from CSV
    }

    Returns:
    {
        "result": "Within budget" | "Above budget",
        "message": "Expected CTC of 45 LPA is above the maximum budget of 40 LPA"
    }
    """
    try:
        data = request.get_json()

        if not data:
            # Return 200 with error info so agent can handle it gracefully
            return jsonify({
                "result": "Error",
                "error": "No data provided",
                "message": "Please provide expected_ctc and max_budget. Proceeding without budget check."
            }), 200

        expected_ctc_str = data.get('expected_ctc', '').strip()
        max_budget_str = data.get('max_budget', '').strip()

        # Validate inputs
        if not expected_ctc_str or not max_budget_str:
            # Return 200 with error info for graceful degradation
            return jsonify({
                "result": "Error",
                "error": "Missing parameters",
                "message": "Both expected_ctc and max_budget are required. Proceeding without budget check."
            }), 200

        # Convert to float for comparison
        try:
            expected_ctc = float(expected_ctc_str)
            max_budget = float(max_budget_str)
        except ValueError:
            # Return 200 with error info
            return jsonify({
                "result": "Error",
                "error": "Invalid number format",
                "message": "expected_ctc and max_budget must be valid numbers. Proceeding without budget check."
            }), 200

        # Validate reasonable ranges (0-200 LPA)
        if expected_ctc < 0 or expected_ctc > 200 or max_budget < 0 or max_budget > 200:
            return jsonify({
                "result": "Error",
                "error": "Invalid range",
                "message": "CTC values must be between 0 and 200 LPA. Proceeding without budget check."
            }), 200

        # Check budget
        if expected_ctc <= max_budget:
            result = "Within budget"
            message = f"Expected CTC of {expected_ctc} LPA is within the maximum budget of {max_budget} LPA"
        else:
            result = "Above budget"
            message = f"Expected CTC of {expected_ctc} LPA is above the maximum budget of {max_budget} LPA"

        return jsonify({
            "result": result,
            "message": message
        }), 200

    except Exception as e:
        # Log the error but return 200 with error info for graceful degradation
        app.logger.error(f"Unexpected error in check_ctc: {str(e)}")
        return jsonify({
            "result": "Error",
            "error": "Server error",
            "message": f"An unexpected error occurred: {str(e)}. Proceeding without budget check."
        }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    import os
    # Use PORT from environment (for Railway/Render) or default to 5001 for local dev
    port = int(os.environ.get('PORT', 5001))
    # Disable debug in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
