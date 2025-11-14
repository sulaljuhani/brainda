import { useEffect, useRef } from 'react';

interface SwipeHandlers {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  onSwipeUp?: () => void;
  onSwipeDown?: () => void;
}

interface SwipeConfig {
  minSwipeDistance?: number;
  preventDefaultTouchMove?: boolean;
}

export function useSwipeGesture(
  elementRef: React.RefObject<HTMLElement>,
  handlers: SwipeHandlers,
  config: SwipeConfig = {}
) {
  const {
    minSwipeDistance = 50,
    preventDefaultTouchMove = false,
  } = config;

  const touchStart = useRef<{ x: number; y: number } | null>(null);
  const touchEnd = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const handleTouchStart = (e: TouchEvent) => {
      touchEnd.current = null;
      touchStart.current = {
        x: e.targetTouches[0].clientX,
        y: e.targetTouches[0].clientY,
      };
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (preventDefaultTouchMove) {
        e.preventDefault();
      }
      touchEnd.current = {
        x: e.targetTouches[0].clientX,
        y: e.targetTouches[0].clientY,
      };
    };

    const handleTouchEnd = () => {
      if (!touchStart.current || !touchEnd.current) return;

      const distanceX = touchStart.current.x - touchEnd.current.x;
      const distanceY = touchStart.current.y - touchEnd.current.y;

      const isHorizontalSwipe = Math.abs(distanceX) > Math.abs(distanceY);
      const isVerticalSwipe = Math.abs(distanceY) > Math.abs(distanceX);

      // Horizontal swipes
      if (isHorizontalSwipe) {
        if (distanceX > minSwipeDistance && handlers.onSwipeLeft) {
          handlers.onSwipeLeft();
        } else if (distanceX < -minSwipeDistance && handlers.onSwipeRight) {
          handlers.onSwipeRight();
        }
      }

      // Vertical swipes
      if (isVerticalSwipe) {
        if (distanceY > minSwipeDistance && handlers.onSwipeUp) {
          handlers.onSwipeUp();
        } else if (distanceY < -minSwipeDistance && handlers.onSwipeDown) {
          handlers.onSwipeDown();
        }
      }

      touchStart.current = null;
      touchEnd.current = null;
    };

    element.addEventListener('touchstart', handleTouchStart, { passive: true });
    element.addEventListener('touchmove', handleTouchMove, {
      passive: !preventDefaultTouchMove
    });
    element.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handlers, minSwipeDistance, preventDefaultTouchMove]);
}
