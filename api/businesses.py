from flask import Blueprint, request, jsonify, g
from datetime import datetime
from api.jwt_authorize import token_required

businesses_api = Blueprint('businesses_api', __name__, url_prefix='/api')

# In-memory storage for businesses (seeded with initial data)
businesses = [
    {
        "id": 1,
        "name": "ActiveMed Integrative Health Center",
        "description": "We believe in a collaborative approach to healthcare. We offer acupuncture, massage therapy, functional medicine, physical therapy, and axon therapy.",
        "address": "11588 Via Rancho San Diego, Suite 101, El Cajon, CA 92019",
        "website": "https://activemedhealth.com/",
        "image": "bus.png",
        "image_layout": "standard",
        "category": "Healthcare",
        "lat": 32.7914,
        "lng": -116.9259,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    },
    {
        "id": 2,
        "name": "Digital One Printing",
        "description": "Digital One Printing is your premier one-stop Poway printshop that offers a wide range of services, has many years of experience and a tremendous reputation. Digital, Offset, Large Format, Posters, Banners, Trade show graphics, Signs, Promotional Products, Bindery and more.",
        "address": "12630 Poway Rd, Poway, CA 92064",
        "website": "https://d1printing.net/",
        "image": "Screenshot 2025-07-23 at 8.34.48 AM.png",
        "image_layout": "wide",
        "category": "Printing Services",
        "lat": 32.9579,
        "lng": -117.0287,
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }
]

# In-memory storage for user spotlights (user_id -> set of business_ids)
user_spotlights = {}

# Counter for new business IDs
business_id_counter = 3


def format_business_response(business):
    """Format a business for API response with coordinates object."""
    return {
        "id": business["id"],
        "name": business["name"],
        "description": business["description"],
        "address": business["address"],
        "website": business["website"],
        "image": business["image"],
        "imageLayout": business.get("image_layout", "standard"),
        "category": business["category"],
        "coordinates": {
            "lat": business["lat"],
            "lng": business["lng"]
        }
    }


def format_business_minimal(business):
    """Format a business with minimal data for spotlight/map display."""
    return {
        "id": business["id"],
        "name": business["name"],
        "address": business["address"],
        "category": business["category"],
        "coordinates": {
            "lat": business["lat"],
            "lng": business["lng"]
        },
        "website": business["website"]
    }


@businesses_api.route('/businesses', methods=['GET'])
def get_businesses():
    """
    Get all active local businesses.
    
    This endpoint is PUBLIC (no authentication required).
    
    Response:
        [
            {
                "id": 1,
                "name": "ActiveMed Integrative Health Center",
                "description": "We believe in a collaborative approach to healthcare...",
                "address": "11588 Via Rancho San Diego, Suite 101, El Cajon, CA 92019",
                "website": "https://activemedhealth.com/",
                "image": "bus.png",
                "imageLayout": "standard",
                "category": "Healthcare",
                "coordinates": { "lat": 32.7914, "lng": -116.9259 }
            },
            ...
        ]
    """
    active_businesses = [b for b in businesses if b.get("is_active", True)]
    return jsonify([format_business_response(b) for b in active_businesses])


@businesses_api.route('/businesses/<int:business_id>', methods=['GET'])
def get_business(business_id):
    """
    Get a single business by ID.
    
    This endpoint is PUBLIC (no authentication required).
    
    Response:
        {
            "id": 1,
            "name": "ActiveMed Integrative Health Center",
            ...
        }
    """
    for business in businesses:
        if business["id"] == business_id and business.get("is_active", True):
            return jsonify(format_business_response(business))
    
    return jsonify({"error": "Business not found"}), 404


@businesses_api.route('/businesses/spotlight', methods=['GET'])
@token_required()
def get_user_spotlights():
    """
    Get the current user's spotlighted business IDs.
    
    This endpoint REQUIRES authentication.
    
    Response:
        {
            "spotlighted_ids": [1, 2]
        }
    """
    current_user = g.current_user
    user_id = current_user.id
    
    # Get user's spotlighted business IDs
    spotlighted_ids = list(user_spotlights.get(user_id, set()))
    
    return jsonify({
        "spotlighted_ids": spotlighted_ids
    })


@businesses_api.route('/businesses/spotlight', methods=['POST'])
@token_required()
def toggle_spotlight():
    """
    Toggle spotlight status for a business.
    
    This endpoint REQUIRES authentication.
    
    Request Body:
        {
            "business_id": 1,
            "spotlight": true
        }
    
    Response:
        {
            "success": true,
            "business_id": 1,
            "spotlight": true
        }
    """
    current_user = g.current_user
    user_id = current_user.id
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    business_id = data.get("business_id")
    spotlight = data.get("spotlight")
    
    if business_id is None:
        return jsonify({"error": "business_id is required"}), 400
    
    if spotlight is None:
        return jsonify({"error": "spotlight (boolean) is required"}), 400
    
    # Verify business exists
    business_exists = any(b["id"] == business_id and b.get("is_active", True) for b in businesses)
    if not business_exists:
        return jsonify({"error": "Business not found"}), 404
    
    # Initialize user's spotlight set if needed
    if user_id not in user_spotlights:
        user_spotlights[user_id] = set()
    
    # Toggle spotlight
    if spotlight:
        user_spotlights[user_id].add(business_id)
    else:
        user_spotlights[user_id].discard(business_id)
    
    return jsonify({
        "success": True,
        "business_id": business_id,
        "spotlight": spotlight
    })


@businesses_api.route('/businesses/spotlight/sync', methods=['POST'])
@token_required()
def sync_spotlights():
    """
    Sync localStorage spotlights with the server.
    
    This endpoint is called when a user logs in to merge their
    localStorage spotlights with their server-side spotlights.
    
    This endpoint REQUIRES authentication.
    
    Request Body:
        {
            "spotlighted_ids": [1, 2, 3]
        }
    
    Response:
        {
            "success": true,
            "spotlighted_ids": [1, 2, 3, 4]  // merged list
        }
    """
    current_user = g.current_user
    user_id = current_user.id
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    local_ids = data.get("spotlighted_ids", [])
    
    # Initialize user's spotlight set if needed
    if user_id not in user_spotlights:
        user_spotlights[user_id] = set()
    
    # Merge local IDs with server IDs
    for bid in local_ids:
        # Only add if business exists and is active
        business_exists = any(b["id"] == bid and b.get("is_active", True) for b in businesses)
        if business_exists:
            user_spotlights[user_id].add(bid)
    
    # Return merged list
    return jsonify({
        "success": True,
        "spotlighted_ids": list(user_spotlights[user_id])
    })


@businesses_api.route('/businesses/spotlight/all', methods=['GET'])
@token_required()
def get_spotlighted_businesses():
    """
    Get full business data for all spotlighted businesses (for map display).
    
    This endpoint REQUIRES authentication.
    
    Response:
        [
            {
                "id": 1,
                "name": "ActiveMed Integrative Health Center",
                "address": "11588 Via Rancho San Diego, Suite 101, El Cajon, CA 92019",
                "category": "Healthcare",
                "coordinates": { "lat": 32.7914, "lng": -116.9259 },
                "website": "https://activemedhealth.com/"
            },
            ...
        ]
    """
    current_user = g.current_user
    user_id = current_user.id
    
    # Get user's spotlighted business IDs
    spotlighted_ids = user_spotlights.get(user_id, set())
    
    # Get full business data for spotlighted businesses
    spotlighted_businesses = [
        format_business_minimal(b) 
        for b in businesses 
        if b["id"] in spotlighted_ids and b.get("is_active", True)
    ]
    
    return jsonify(spotlighted_businesses)


# Admin endpoints for managing businesses (optional)

@businesses_api.route('/businesses', methods=['POST'])
@token_required(roles=["Admin"])
def create_business():
    """
    Create a new business (Admin only).
    
    Request Body:
        {
            "name": "Business Name",
            "description": "Description",
            "address": "123 Main St",
            "website": "https://example.com",
            "image": "image.png",
            "image_layout": "standard",
            "category": "Category",
            "lat": 32.7157,
            "lng": -117.1611
        }
    
    Response:
        {
            "message": "Business created successfully",
            "business": { ...business data... }
        }
    """
    global business_id_counter
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    # Validate required fields
    required_fields = ["name", "address", "category", "lat", "lng"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400
    
    # Create the business
    business = {
        "id": business_id_counter,
        "name": data["name"],
        "description": data.get("description", ""),
        "address": data["address"],
        "website": data.get("website", ""),
        "image": data.get("image", ""),
        "image_layout": data.get("image_layout", "standard"),
        "category": data["category"],
        "lat": data["lat"],
        "lng": data["lng"],
        "created_at": datetime.utcnow().isoformat(),
        "is_active": True
    }
    
    businesses.append(business)
    business_id_counter += 1
    
    return jsonify({
        "message": "Business created successfully",
        "business": format_business_response(business)
    }), 201


@businesses_api.route('/businesses/<int:business_id>', methods=['PUT'])
@token_required(roles=["Admin"])
def update_business(business_id):
    """
    Update a business (Admin only).
    
    Request Body:
        {
            "name": "Updated Name",
            ...other fields to update...
        }
    
    Response:
        {
            "message": "Business updated successfully",
            "business": { ...updated business data... }
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400
    
    # Find the business
    for business in businesses:
        if business["id"] == business_id:
            # Update allowed fields
            allowed_fields = ["name", "description", "address", "website", "image", "image_layout", "category", "lat", "lng", "is_active"]
            for field in allowed_fields:
                if field in data:
                    business[field] = data[field]
            
            return jsonify({
                "message": "Business updated successfully",
                "business": format_business_response(business)
            })
    
    return jsonify({"error": "Business not found"}), 404


@businesses_api.route('/businesses/<int:business_id>', methods=['DELETE'])
@token_required(roles=["Admin"])
def delete_business(business_id):
    """
    Delete a business (Admin only).
    
    This performs a soft delete by setting is_active to False.
    
    Response:
        {
            "message": "Business deleted successfully"
        }
    """
    for business in businesses:
        if business["id"] == business_id:
            business["is_active"] = False
            
            # Remove from all user spotlights
            for user_id in user_spotlights:
                user_spotlights[user_id].discard(business_id)
            
            return jsonify({"message": "Business deleted successfully"})
    
    return jsonify({"error": "Business not found"}), 404
