#!/bin/bash

echo "🔄 Resetting frontend to original state..."

# Remove existing frontend
rm -rf ../frontend

# Create fresh frontend structure
mkdir -p ../frontend/src

# Copy all the files from above into their respective locations
# You'll need to manually create these files with the content above

echo "✅ Frontend reset complete"
echo "📁 Frontend structure created at: ../frontend/"
echo ""
echo "📝 Next steps:"
echo "1. Copy the code above into the respective files"
echo "2. Run: docker-compose -f deploy/docker-compose.yml build frontend"
echo "3. Run: docker-compose -f deploy/docker-compose.yml up -d"