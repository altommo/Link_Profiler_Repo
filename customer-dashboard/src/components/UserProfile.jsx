import React, { useState, useEffect } from 'react';
// Assuming you'll have an API service to fetch/update user data
// import { getUserProfile, updateProfile } from '../services/api'; 

const UserProfile = ({ user }) => {
  const [profileData, setProfileData] = useState({
    username: '',
    email: '',
    // Add other fields like organization, subscription tier, etc.
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        // In a real application, you'd fetch data from your backend API
        // const data = await getUserProfile(user.id); 
        
        // Simulate API call
        const simulatedData = {
          username: user ? user.username : 'GuestUser',
          email: user ? user.email : 'guest@example.com',
          organization: 'Acme Corp',
          subscriptionTier: 'Premium',
          apiCallsRemaining: 5000,
          crawlCreditsRemaining: 200,
        };
        setProfileData(simulatedData);
      } catch (err) {
        setError('Failed to fetch profile data. Please try again later.');
        console.error('Error fetching profile:', err);
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchProfile();
    }
  }, [user]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfileData(prevData => ({
      ...prevData,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      // In a real application, you'd send updated data to your backend API
      // await updateProfile(user.id, profileData);
      setMessage('Profile updated successfully!');
      setIsEditing(false);
    } catch (err) {
      setError('Failed to update profile. Please try again.');
      console.error('Error updating profile:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading-message">Loading profile...</div>;
  }

  if (error) {
    return <div className="error-message">{error}</div>;
  }

  return (
    <div className="user-profile-container">
      <h2>Your Profile</h2>
      <p>Manage your account details and subscription information.</p>

      {message && <div className="success-message">{message}</div>}

      <form onSubmit={handleSubmit}>
        <div className="profile-field">
          <label htmlFor="username">Username:</label>
          {isEditing ? (
            <input
              type="text"
              id="username"
              name="username"
              value={profileData.username}
              onChange={handleChange}
              required
            />
          ) : (
            <span>{profileData.username}</span>
          )}
        </div>

        <div className="profile-field">
          <label htmlFor="email">Email:</label>
          {isEditing ? (
            <input
              type="email"
              id="email"
              name="email"
              value={profileData.email}
              onChange={handleChange}
              required
            />
          ) : (
            <span>{profileData.email}</span>
          )}
        </div>

        <div className="profile-field">
          <label>Organization:</label>
          <span>{profileData.organization}</span>
        </div>

        <div className="profile-field">
          <label>Subscription Tier:</label>
          <span>{profileData.subscriptionTier}</span>
        </div>

        <div className="profile-field">
          <label>API Calls Remaining (Monthly):</label>
          <span>{profileData.apiCallsRemaining}</span>
        </div>

        <div className="profile-field">
          <label>Crawl Credits Remaining:</label>
          <span>{profileData.crawlCreditsRemaining}</span>
        </div>

        <div className="profile-actions">
          {isEditing ? (
            <>
              <button type="submit" className="save-button" disabled={loading}>
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
              <button type="button" className="cancel-button" onClick={() => setIsEditing(false)} disabled={loading}>
                Cancel
              </button>
            </>
          ) : (
            <button type="button" className="edit-button" onClick={() => setIsEditing(true)}>
              Edit Profile
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default UserProfile;
