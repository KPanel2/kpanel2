apt update
apt install sudo -y
apt install gnupg -y
apt install gnupg1 -y
apt install gnupg2 -y
wget -O- http://debian.kumpeapps.com/public.gpg |\
    gpg --dearmor |\
    sudo tee /usr/share/keyrings/KumpeApps.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/KumpeApps.gpg] http://debian.kumpeapps.com stable main" > /etc/apt/sources.list.d/KumpeApps.list
apt update
