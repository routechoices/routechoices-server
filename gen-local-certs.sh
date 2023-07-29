#!/bin/bash
set -e
NAME=routechoices
DOMAIN=routechoices.dev # Use your own domain name

mkdir -p "letsencrypt/live/${DOMAIN}/"
cd "letsencrypt/live/${DOMAIN}/"

######################
# Become a Certificate Authority
######################

# Generate private key
openssl genrsa -out ${NAME}CA.key 2048
# Generate root certificate
openssl req -x509 -new -nodes -key ${NAME}CA.key -sha256 \
    -subj "/C=FI/ST=${NAME}/L=${NAME}/O=${NAME}/OU=${NAME}/CN=${DOMAIN}/emailAddress=root@${DOMAIN}" \
    -days 825 -out ${NAME}CA.pem

######################
# Create CA-signed certs
######################
# Generate a private key
openssl genrsa -out privkey.pem 2048
# Create a certificate-signing request
openssl req -new \
    -subj "/C=FI/ST=${NAME}/L=${NAME}/O=${NAME}/OU=${NAME}/CN=${DOMAIN}/emailAddress=root@${DOMAIN}" \
    -key privkey.pem -out ${DOMAIN}.csr
# Create a config file for the extensions
>${DOMAIN}.ext cat <<-EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = ${DOMAIN} # Be sure to include the domain name here because Common Name is not so commonly honoured by itself
DNS.2 = *.${DOMAIN} # Optionally, add additional domains (I've added a subdomain here)
EOF
# Create the signed certificate
openssl x509 -req -in ${DOMAIN}.csr -CA ${NAME}CA.pem -CAkey ${NAME}CA.key -CAcreateserial \
    -out fullchain.pem -days 825 -sha256 -extfile ${DOMAIN}.ext

rm -f ${NAME}CA.key ${NAME}CA.srl ${DOMAIN}.csr ${DOMAIN}.ext

echo "Local certificates created succesfully! Adding ${NAME}CA certificate to keychain to enable local HTTPS..."
unameOut="$(uname -s)"
case "${unameOut}" in
    Linux*)     machine=Linux;;
    Darwin*)    machine=Mac;;
    *)          machine="UNKNOWN:${unameOut}"
esac
if [ "$(uname)" == "Mac" ]; then
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ${NAME}CA.pem
elif [ "$(uname)" == "Linux" ]; then
    sudo cp ${NAME}CA.pem /usr/local/share/ca-certificates/${NAME}CA.crt
    sudo update-ca-certificates
fi
