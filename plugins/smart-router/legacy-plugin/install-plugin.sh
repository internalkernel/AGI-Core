#!/bin/bash
# install-plugin.sh

echo "🎯 Installing Smart Router Plugin"
echo "=================================="

# Build the plugin
echo "Building plugin..."
npm install
npm run build

# Create plugin directory
PLUGIN_DIR="$HOME/.openclaw/extensions/smart-router"
mkdir -p "$PLUGIN_DIR"

# Copy files
echo "Installing plugin..."
cp -r dist "$PLUGIN_DIR/"
cp package.json "$PLUGIN_DIR/"
cp openclaw.plugin.json "$PLUGIN_DIR/"

# Install dependencies in plugin directory
cd "$PLUGIN_DIR"
npm install --production

echo "✓ Plugin installed to $PLUGIN_DIR"
echo ""
echo "Next steps:"
echo "1. Set API keys in ~/.bashrc or ~/.zshrc:"
echo "   export ANTHROPIC_API_KEY='sk-ant-...'"
echo "   export OPENAI_API_KEY='sk-...'"
echo "   export GOOGLE_API_KEY='...'"
echo ""
echo "2. Enable plugin in ~/.openclaw/openclaw.json:"
echo '   "plugins": ["@local/smart-router"]'
echo ""
echo "3. Set as default model:"
echo '   "model": "smart-router/auto"'
echo ""
echo "4. Restart OpenClaw:"
echo "   openclaw gateway restart"
