import * as React from 'react';
import { cn } from '@/lib/utils';
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => <input ref={ref} className={cn('flex h-11 w-full min-w-0 rounded-md border border-input bg-card px-3 py-2 text-[15px] disabled:opacity-50', className)} {...props} />);
Input.displayName = 'Input';
