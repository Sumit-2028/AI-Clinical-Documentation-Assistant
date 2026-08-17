import type { ReactNode, SVGProps } from 'react'
type IconProps = SVGProps<SVGSVGElement>
const Icon = ({ children, ...props }: IconProps & { children: ReactNode }) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>
export const ActivityIcon = (props: IconProps) => <Icon {...props}><path d="M3 12h4l2.2-7 4.1 14L16 12h5" /></Icon>
export const ArchiveIcon = (props: IconProps) => <Icon {...props}><path d="M4 7h16M6 7v12h12V7M9 11h6M5 3h14l1 4H4l1-4Z" /></Icon>
export const ClipboardIcon = (props: IconProps) => <Icon {...props}><path d="M9 5h6M9 3h6v4H9zM6 5H4v16h16V5h-2M8 12h8M8 16h5" /></Icon>
export const FileIcon = (props: IconProps) => <Icon {...props}><path d="M6 3h8l4 4v14H6zM14 3v5h5M9 13h6M9 17h6" /></Icon>
export const GridIcon = (props: IconProps) => <Icon {...props}><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></Icon>
export const HeartIcon = (props: IconProps) => <Icon {...props}><path d="M20.8 8.8c0 5.1-8.8 10-8.8 10s-8.8-4.9-8.8-10A4.8 4.8 0 0 1 12 5.6a4.8 4.8 0 0 1 8.8 3.2Z" /></Icon>
export const SearchIcon = (props: IconProps) => <Icon {...props}><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></Icon>
export const ChevronIcon = (props: IconProps) => <Icon {...props}><path d="m9 18 6-6-6-6"/></Icon>
export const UploadIcon = (props: IconProps) => <Icon {...props}><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v5h14v-5"/></Icon>
export const CheckIcon = (props: IconProps) => <Icon {...props}><path d="m5 12 4 4L19 6"/></Icon>
export const AlertIcon = (props: IconProps) => <Icon {...props}><path d="M12 4 3 20h18L12 4Z"/><path d="M12 10v4m0 3h.01"/></Icon>
export const ClockIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/></Icon>
export const UserIcon = (props: IconProps) => <Icon {...props}><circle cx="12" cy="8" r="3"/><path d="M5 21a7 7 0 0 1 14 0"/></Icon>
export const BellIcon = (props: IconProps) => <Icon {...props}><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></Icon>
export const MoreIcon = (props: IconProps) => <Icon {...props}><circle cx="5" cy="12" r=".7" fill="currentColor"/><circle cx="12" cy="12" r=".7" fill="currentColor"/><circle cx="19" cy="12" r=".7" fill="currentColor"/></Icon>
export const ArrowIcon = (props: IconProps) => <Icon {...props}><path d="M5 12h13m-5-5 5 5-5 5"/></Icon>
export const XIcon = (props: IconProps) => <Icon {...props}><path d="m6 6 12 12M18 6 6 18"/></Icon>
