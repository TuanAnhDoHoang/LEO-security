import datetime
import os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID

def generate_ca():
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"VN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"HCMC"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"District 1"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"LEO-SAT Network CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"LEO-SAT Root CA"),
    ])
    
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now
    ).not_valid_after(
        now + datetime.timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).sign(private_key, None)
    
    return private_key, cert

def generate_cert(ca_key, ca_cert, name):
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"VN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"LEO-SAT Ground Station"),
        x509.NameAttribute(NameOID.COMMON_NAME, name),
    ])
    
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        ca_cert.subject
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now
    ).not_valid_after(
        now + datetime.timedelta(days=365)
    ).sign(ca_key, None)
    
    return private_key, cert

def save_key(key, filename):
    with open(filename, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

def save_cert(cert, filename):
    with open(filename, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def main():
    os.makedirs("eavesdropper/certs", exist_ok=True)
    
    print("Generating CA...")
    ca_key, ca_cert = generate_ca()
    save_key(ca_key, "eavesdropper/certs/ca.key")
    save_cert(ca_cert, "eavesdropper/certs/ca.crt")
    
    print("Generating Sender Cert (GS-46)...")
    s_key, s_cert = generate_cert(ca_key, ca_cert, u"GS-46-HCMC")
    save_key(s_key, "eavesdropper/certs/sender.key")
    save_cert(s_cert, "eavesdropper/certs/sender.crt")
    
    print("Generating Receiver Cert (GS-63)...")
    r_key, r_cert = generate_cert(ca_key, ca_cert, u"GS-63-Singapore")
    save_key(r_key, "eavesdropper/certs/receiver.key")
    save_cert(r_cert, "eavesdropper/certs/receiver.crt")
    
    print("Done! Certificates generated in eavesdropper/certs/")

if __name__ == "__main__":
    main()
