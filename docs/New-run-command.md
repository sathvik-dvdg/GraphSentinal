project blockchain
cd d:\GraphSentinal\blockchain
npx ganache --host 0.0.0.0 --port 8545 --deterministic --accounts 5 --db ./ganache-data

term 2
cd d:\GraphSentinal\blockchain
npx hardhat run scripts/deploy.js --network localhost

term 3 backend
cd d:\GraphSentinal\backend
source .venv/bin/activate
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload

term 4 frontend
cd d:\GraphSentinal\frontend
npm run dev