import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useLocalStorage } from './useLocalStorage';

describe('useLocalStorage', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('initializes with the provided initial value', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    expect(result.current[0]).toBe('initial');
  });

  it('reads existing value from localStorage', () => {
    localStorage.setItem('test-key', JSON.stringify('stored-value'));

    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    expect(result.current[0]).toBe('stored-value');
  });

  it('updates localStorage when value is set', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    act(() => {
      result.current[1]('new-value');
    });

    expect(result.current[0]).toBe('new-value');
    expect(localStorage.setItem).toHaveBeenCalledWith('test-key', JSON.stringify('new-value'));
  });

  it('handles complex objects', () => {
    const initialValue = { name: 'Test', count: 0 };
    const { result } = renderHook(() => useLocalStorage('test-key', initialValue));

    expect(result.current[0]).toEqual(initialValue);

    const newValue = { name: 'Updated', count: 5 };
    act(() => {
      result.current[1](newValue);
    });

    expect(result.current[0]).toEqual(newValue);
    expect(localStorage.setItem).toHaveBeenCalledWith('test-key', JSON.stringify(newValue));
  });

  it('handles arrays', () => {
    const initialValue = [1, 2, 3];
    const { result } = renderHook(() => useLocalStorage('test-key', initialValue));

    expect(result.current[0]).toEqual(initialValue);

    const newValue = [4, 5, 6];
    act(() => {
      result.current[1](newValue);
    });

    expect(result.current[0]).toEqual(newValue);
  });

  it('handles boolean values', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', false));

    expect(result.current[0]).toBe(false);

    act(() => {
      result.current[1](true);
    });

    expect(result.current[0]).toBe(true);
  });

  it('handles numbers', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 42));

    expect(result.current[0]).toBe(42);

    act(() => {
      result.current[1](100);
    });

    expect(result.current[0]).toBe(100);
  });

  it('returns initial value on parse error', () => {
    // Set invalid JSON
    (localStorage.getItem as any).mockReturnValue('invalid-json{');

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { result } = renderHook(() => useLocalStorage('test-key', 'fallback'));

    expect(result.current[0]).toBe('fallback');
    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  it('handles localStorage setItem errors gracefully', () => {
    (localStorage.setItem as any).mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const { result } = renderHook(() => useLocalStorage('test-key', 'initial'));

    act(() => {
      result.current[1]('new-value');
    });

    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  it('persists across hook re-renders', () => {
    const { result, rerender } = renderHook(() => useLocalStorage('test-key', 'initial'));

    act(() => {
      result.current[1]('updated');
    });

    rerender();

    expect(result.current[0]).toBe('updated');
  });

  it('uses different keys independently', () => {
    const { result: result1 } = renderHook(() => useLocalStorage('key1', 'value1'));
    const { result: result2 } = renderHook(() => useLocalStorage('key2', 'value2'));

    expect(result1.current[0]).toBe('value1');
    expect(result2.current[0]).toBe('value2');

    act(() => {
      result1.current[1]('updated1');
    });

    expect(result1.current[0]).toBe('updated1');
    expect(result2.current[0]).toBe('value2');
  });
});
