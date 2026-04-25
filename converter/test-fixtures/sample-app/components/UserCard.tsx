import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { formatDate } from "../utils/date";

interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl: string;
  role: "admin" | "user" | "moderator";
  createdAt: string;
}

interface UserCardProps {
  userId: string;
  showActions?: boolean;
}

export function UserCard({ userId, showActions = true }: UserCardProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFavorite, setIsFavorite] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    async function loadUser() {
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}`);
        const data = await response.json();
        setUser(data);
      } catch (error) {
        console.error("Failed to load user:", error);
      } finally {
        setIsLoading(false);
      }
    }
    loadUser();
  }, [userId]);

  useEffect(() => {
    const saved = localStorage.getItem(`favorite-${userId}`);
    if (saved) setIsFavorite(JSON.parse(saved));
  }, [userId]);

  const handleFavorite = () => {
    const newValue = !isFavorite;
    setIsFavorite(newValue);
    localStorage.setItem(`favorite-${userId}`, JSON.stringify(newValue));
  };

  if (isLoading) {
    return <div className="animate-pulse bg-gray-200 rounded-lg h-32 w-full" />;
  }

  if (!user) {
    return <div className="text-red-500 text-center p-4">User not found</div>;
  }

  return (
    <div className="bg-white rounded-xl shadow-md p-6 flex flex-col items-center gap-4">
      <img
        src={user.avatarUrl}
        alt={user.name}
        className="w-20 h-20 rounded-full object-cover"
      />
      <div className="text-center">
        <h2 className="text-xl font-bold text-gray-900">{user.name}</h2>
        <p className="text-sm text-gray-500">{user.email}</p>
        <span className="inline-block mt-1 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
          {user.role}
        </span>
      </div>
      <p className="text-xs text-gray-400">Joined {formatDate(user.createdAt)}</p>
      {showActions && (
        <div className="flex gap-2 w-full">
          <button
            onClick={() => navigate(`/users/${user.id}`)}
            className="flex-1 bg-blue-500 text-white py-2 rounded-lg hover:bg-blue-600 transition"
          >
            View Profile
          </button>
          <button
            onClick={handleFavorite}
            className={`px-4 py-2 rounded-lg transition ${
              isFavorite ? "bg-yellow-400 text-yellow-900" : "bg-gray-100 text-gray-600"
            }`}
          >
            {isFavorite ? "★" : "☆"}
          </button>
        </div>
      )}
    </div>
  );
}
