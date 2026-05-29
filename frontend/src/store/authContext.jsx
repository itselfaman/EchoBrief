import React, { createContext, useContext, useEffect, useRef, useState } from 'react';
import { supabase } from '../supabaseClient';

const AuthContext = createContext(null);

/**
 * AuthProvider — wraps the app and provides Supabase session state.
 *
 * FIX: Drop the redundant `getSession()` call that raced with `onAuthStateChange`.
 *
 * Supabase's `onAuthStateChange` already fires an `INITIAL_SESSION` event
 * synchronously-ish on mount (it resolves from localStorage), which is the
 * single source of truth. Calling `getSession()` in parallel created a race:
 *
 *   t=0  session = undefined  (isLoading = true)
 *   t=1  onAuthStateChange fires INITIAL_SESSION → session = <value>
 *   t=2  getSession() resolves → session = <value again> (double setState → extra render)
 *
 * In React 18 Strict Mode the effect runs twice. The second mount re-subscribes
 * while the first subscription's cleanup hasn't fully propagated, so auth state
 * briefly resets to null between the two mounts — triggering route guards.
 *
 * Solution:
 * - Use a `mountedRef` so we only update state if the component is still mounted.
 * - Use `onAuthStateChange` alone as the single source of truth.
 * - Start `isLoading = true` (session = undefined), flip to false on first event.
 */
export function AuthProvider({ children }) {
  // undefined = still loading (haven't heard from Supabase yet)
  // null      = loaded, no session
  // Session   = loaded, authenticated
  const [session, setSession] = useState(undefined);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    // onAuthStateChange fires INITIAL_SESSION immediately from localStorage,
    // then TOKEN_REFRESHED / SIGNED_IN / SIGNED_OUT on subsequent changes.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      if (!mountedRef.current) return;
      // null means "no session" — differentiate from undefined ("still loading")
      setSession(newSession ?? null);
    });

    return () => {
      mountedRef.current = false;
      subscription.unsubscribe();
    };
  }, []); // empty deps — subscribe once, unsubscribe on unmount

  const signOut = async () => {
    // Don't navigate here — let route guards react to the session change.
    await supabase.auth.signOut();
  };

  const value = {
    session,
    user: session?.user ?? null,
    // isLoading is true only while session === undefined (before first Supabase event)
    isLoading: session === undefined,
    isAuthenticated: !!session,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * useAuth — hook to access authentication state anywhere in the component tree.
 */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
