cat > /etc/profile.d/cuda.sh <<'EOF'
export CUDA_HOME=/usr/local/cuda
export PATH="$CUDA_HOME/bin:$PATH"
EOF

printf '/usr/lib64-nvidia\n' > /etc/ld.so.conf.d/nvidia.conf
ldconfig

ln -sf /usr/local/cuda/bin/nvcc /usr/local/bin/nvcc

source /etc/profile.d/cuda.sh

echo '=== NVIDIA ==='
nvidia-smi

echo
echo '=== CUDA ==='
which nvcc
nvcc --version

echo
echo '=== ENVIRONMENT ==='
echo "CUDA_HOME=$CUDA_HOME"
echo "PATH=$PATH"
