source /mnt/d/GraphSentinal/backend/.venv/bin/activate
python -c "import torch; print('Torch in WSL:', torch.__version__, '| CUDA:', torch.cuda.is_available())"
