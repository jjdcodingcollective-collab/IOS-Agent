# Code Analysis Report

> Generated: 2026-04-25T05:29:16.350230+00:00
> Source: `/storage/users/user_3AeOuDUrxI7LrpU6J21FpMneayM/projects/ios-agent/converter/test-fixtures/sample-app`

## Overview

| Metric | Value |
|---|---|
| Total files scanned | 4 |
| Total patterns detected | 46 |
| Auto-convertible patterns | 38 |
| Needs assistance | 8 |
| Manual conversion needed | 0 |

**Conversion readiness: 83% auto-convertible**

## File Types

| Type | Count | iOS Equivalent |
|---|---|---|
| component | 1 | SwiftUI View struct |
| hook | 1 | @Observable ViewModel |
| service | 1 | Service struct / APIClient |
| unknown | 1 | (needs manual classification) |

## Detected Patterns

| Pattern | Count |
|---|---|
| hook | 11 |
| api_call | 10 |
| type_definition | 7 |
| storage | 7 |
| env_variable | 5 |
| custom_hook | 2 |
| component | 1 |
| routing | 1 |
| styling | 1 |
| state_management | 1 |

## Third-Party Dependencies

These will need Swift equivalents or removal:

- `axios`
- `date-fns`
- `react`
- `react-router-dom`

## Environment Variables

These need to move to xcconfig / Info.plist:

- `NEXT_PUBLIC_API_URL`

## API Endpoints

These will be called via URLSession/APIClient:

| Method | URL | Source File |
|---|---|---|
| GET | `${process.env.NEXT_PUBLIC_API_URL}/users/${userId}` | components/UserCard.tsx |
| GET | `${API_BASE}/articles` | services/articleService.ts |
| GET | `${API_BASE}/articles/${id}` | services/articleService.ts |
| POST | `${API_BASE}/articles` | services/articleService.ts |
| PUT | `${API_BASE}/articles/${id}` | services/articleService.ts |
| DELETE | `${API_BASE}/articles/${id}` | services/articleService.ts |
| GET | `${API_BASE}/articles/search` | services/articleService.ts |
| GET | `${process.env.NEXT_PUBLIC_API_URL}/auth/me` | hooks/useAuth.ts |
| GET | `${process.env.NEXT_PUBLIC_API_URL}/auth/login` | hooks/useAuth.ts |
| GET | `${process.env.NEXT_PUBLIC_API_URL}/auth/refresh` | hooks/useAuth.ts |

## File-by-File Analysis

### `components/UserCard.tsx` (component)

- [AUTO] **component**: `UserCard` (line 19)
- [AUTO] **hook**: `useState` (line 20) -> `@State`
- [AUTO] **hook**: `useState` (line 21) -> `@State`
- [AUTO] **hook**: `useState` (line 22) -> `@State`
- [ASSISTED] **hook**: `useEffect` (line 25) -> `.task / .onAppear / .onChange`
- [ASSISTED] **hook**: `useEffect` (line 40) -> `.task / .onAppear / .onChange`
- [ASSISTED] **hook**: `useNavigate` (line 23) -> `NavigationPath / @Environment(\.dismiss)`
- [AUTO] **api_call**: `fetch` (line 28) -> `URLSession.shared.data(from:)`
- [ASSISTED] **routing**: `navigate-hook` (line 23) -> `NavigationStack / NavigationLink`
- [ASSISTED] **styling**: `tailwind` (line 1) -> `SwiftUI modifiers`
- [AUTO] **type_definition**: `User` (line 5) -> `struct: Codable`
- [AUTO] **type_definition**: `UserCardProps` (line 14) -> `struct: Codable`
- [AUTO] **env_variable**: `NEXT_PUBLIC_API_URL` (line 28) -> `xcconfig / Info.plist / Bundle.main`
- [AUTO] **storage**: `localStorage` (line 41) -> `UserDefaults or Keychain`
- [AUTO] **storage**: `localStorage` (line 48) -> `UserDefaults or Keychain`

### `services/articleService.ts` (service)

- [AUTO] **api_call**: `axios.get` (line 31) -> `APIClient`
- [AUTO] **api_call**: `axios.get` (line 38) -> `APIClient`
- [AUTO] **api_call**: `axios.post` (line 43) -> `APIClient`
- [AUTO] **api_call**: `axios.put` (line 50) -> `APIClient`
- [AUTO] **api_call**: `axios.delete` (line 57) -> `APIClient`
- [AUTO] **api_call**: `axios.get` (line 63) -> `APIClient`
- [AUTO] **type_definition**: `Article` (line 5) -> `struct: Codable`
- [AUTO] **type_definition**: `CreateArticleInput` (line 21) -> `struct: Codable`
- [AUTO] **type_definition**: `ArticleSortBy` (line 27) -> `typealias or enum`
- [AUTO] **env_variable**: `NEXT_PUBLIC_API_URL` (line 3) -> `xcconfig / Info.plist / Bundle.main`

### `hooks/useAuth.ts` (hook)

- [AUTO] **hook**: `useState` (line 25) -> `@State`
- [AUTO] **hook**: `useState` (line 26) -> `@State`
- [AUTO] **hook**: `useState` (line 27) -> `@State`
- [ASSISTED] **hook**: `useEffect` (line 29) -> `.task / .onAppear / .onChange`
- [AUTO] **hook**: `useContext` (line 19) -> `@Environment`
- [ASSISTED] **custom_hook**: `useAuth` (line 18) -> `@Observable ViewModel`
- [ASSISTED] **custom_hook**: `useAuthProvider` (line 24) -> `@Observable ViewModel`
- [AUTO] **state_management**: `createContext` (line 16) -> `@Observable / @Environment`
- [AUTO] **api_call**: `fetch` (line 41) -> `URLSession.shared.data(from:)`
- [AUTO] **api_call**: `fetch` (line 59) -> `URLSession.shared.data(from:)`
- [AUTO] **api_call**: `fetch` (line 81) -> `URLSession.shared.data(from:)`
- [AUTO] **type_definition**: `AuthState` (line 3) -> `struct: Codable`
- [AUTO] **type_definition**: `AuthContextType` (line 10) -> `struct: Codable`
- [AUTO] **env_variable**: `NEXT_PUBLIC_API_URL` (line 41) -> `xcconfig / Info.plist / Bundle.main`
- [AUTO] **env_variable**: `NEXT_PUBLIC_API_URL` (line 59) -> `xcconfig / Info.plist / Bundle.main`
- [AUTO] **env_variable**: `NEXT_PUBLIC_API_URL` (line 81) -> `xcconfig / Info.plist / Bundle.main`
- [AUTO] **storage**: `localStorage` (line 30) -> `UserDefaults or Keychain`
- [AUTO] **storage**: `localStorage` (line 48) -> `UserDefaults or Keychain`
- [AUTO] **storage**: `localStorage` (line 70) -> `UserDefaults or Keychain`
- [AUTO] **storage**: `localStorage` (line 76) -> `UserDefaults or Keychain`
- [AUTO] **storage**: `localStorage` (line 88) -> `UserDefaults or Keychain`
