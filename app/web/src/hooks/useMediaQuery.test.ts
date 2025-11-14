import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import {
  useMediaQuery,
  useIsMobile,
  useIsTablet,
  useIsDesktop,
  useIsMobileOrTablet,
} from './useMediaQuery';

describe('useMediaQuery', () => {
  let mediaQueryLists: Map<string, MediaQueryList>;

  beforeEach(() => {
    mediaQueryLists = new Map();

    // Mock window.matchMedia
    window.matchMedia = vi.fn().mockImplementation((query: string) => {
      if (!mediaQueryLists.has(query)) {
        const mql: Partial<MediaQueryList> = {
          matches: false,
          media: query,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          addListener: vi.fn(),
          removeListener: vi.fn(),
        };
        mediaQueryLists.set(query, mql as MediaQueryList);
      }
      return mediaQueryLists.get(query);
    });
  });

  it('returns initial false when query does not match', () => {
    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));
    expect(result.current).toBe(false);
  });

  it('returns initial true when query matches', () => {
    const mockMql = {
      matches: true,
      media: '(min-width: 768px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));
    expect(result.current).toBe(true);
  });

  it('updates when media query changes (modern API)', () => {
    let listener: ((e: MediaQueryListEvent) => void) | null = null;
    const mockMql = {
      matches: false,
      media: '(min-width: 768px)',
      addEventListener: vi.fn((_, cb) => {
        listener = cb;
      }),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));

    expect(result.current).toBe(false);

    // Simulate media query change
    act(() => {
      listener?.({ matches: true } as MediaQueryListEvent);
    });

    expect(result.current).toBe(true);
  });

  it('updates when media query changes (legacy API)', () => {
    let listener: ((e: MediaQueryListEvent) => void) | null = null;
    const mockMql = {
      matches: false,
      media: '(min-width: 768px)',
      addListener: vi.fn((cb) => {
        listener = cb;
      }),
      removeListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'));

    expect(result.current).toBe(false);

    // Simulate media query change
    act(() => {
      listener?.({ matches: true } as MediaQueryListEvent);
    });

    expect(result.current).toBe(true);
  });

  it('cleans up event listener on unmount (modern API)', () => {
    const mockMql = {
      matches: false,
      media: '(min-width: 768px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'));

    unmount();

    expect(mockMql.removeEventListener).toHaveBeenCalled();
  });

  it('cleans up event listener on unmount (legacy API)', () => {
    const mockMql = {
      matches: false,
      media: '(min-width: 768px)',
      addListener: vi.fn(),
      removeListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { unmount } = renderHook(() => useMediaQuery('(min-width: 768px)'));

    unmount();

    expect(mockMql.removeListener).toHaveBeenCalled();
  });

  it('updates when query prop changes', () => {
    const { result, rerender } = renderHook(
      ({ query }) => useMediaQuery(query),
      { initialProps: { query: '(min-width: 768px)' } }
    );

    expect(result.current).toBe(false);

    rerender({ query: '(max-width: 767px)' });

    // Should re-subscribe with new query
    expect(window.matchMedia).toHaveBeenCalledWith('(max-width: 767px)');
  });
});

describe('useIsMobile', () => {
  it('returns true for mobile viewport', () => {
    const mockMql = {
      matches: true,
      media: '(max-width: 767px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it('returns false for non-mobile viewport', () => {
    const mockMql = {
      matches: false,
      media: '(max-width: 767px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});

describe('useIsTablet', () => {
  it('returns true for tablet viewport', () => {
    const mockMql = {
      matches: true,
      media: '(min-width: 768px) and (max-width: 1023px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsTablet());
    expect(result.current).toBe(true);
  });
});

describe('useIsDesktop', () => {
  it('returns true for desktop viewport', () => {
    const mockMql = {
      matches: true,
      media: '(min-width: 1024px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsDesktop());
    expect(result.current).toBe(true);
  });
});

describe('useIsMobileOrTablet', () => {
  it('returns true for mobile or tablet viewport', () => {
    const mockMql = {
      matches: true,
      media: '(max-width: 1023px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsMobileOrTablet());
    expect(result.current).toBe(true);
  });

  it('returns false for desktop viewport', () => {
    const mockMql = {
      matches: false,
      media: '(max-width: 1023px)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    } as any;

    window.matchMedia = vi.fn().mockReturnValue(mockMql);

    const { result } = renderHook(() => useIsMobileOrTablet());
    expect(result.current).toBe(false);
  });
});
