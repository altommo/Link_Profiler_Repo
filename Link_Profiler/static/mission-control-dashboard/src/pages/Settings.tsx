        // Fetch API Keys
        const apiKeysResponse = await fetch(`${API_BASE_URL}/admin/api_keys`, { headers });
        if (!apiKeysResponse.ok) {
          const errorData = await apiKeysResponse.json();
          throw new Error(errorData.detail || 'Failed to fetch API keys');
        }
        const apiKeysData: ApiKeyInfo[] = await apiKeysResponse.json();
        setApiKeys(apiKeysData);
