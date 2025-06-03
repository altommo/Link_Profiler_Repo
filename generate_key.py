import secrets



# Generate a URL-safe text string, containing 32 random bytes.

# This results in a string of approximately 43 characters.

secret_key = secrets.token_urlsafe(32)



print("Generated Secret Key:")

print(secret_key)

print("\nUse this key for your LP_AUTH_SECRET_KEY environment variable.")

print("Example: export LP_AUTH_SECRET_KEY='YOUR_GENERATED_KEY_HERE'")