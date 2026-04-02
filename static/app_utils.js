const safeClamp = (num, min, max) => {
    [min, max] = [Math.min(min, max), Math.max(min, max)]; // enforce min <= max
    return Math.min(Math.max(num, min), max);
};
const delay = async (ms) => new Promise(res => setTimeout(res, ms));

function transformTimestamp(timestamp) {
    return `${getTransformedTime(timestamp)} - ${getTransformedDate(timestamp)}`;
}
function getTransformedDate(timestamp) {
    const datePart = timestamp.split('_')[0];

    const year = datePart.slice(0, 4);
    const month = datePart.slice(4, 6);
    const day = datePart.slice(6, 8);

    const formattedDate = `${day}.${month}.${year}`;

    return `${formattedDate}`;
}
function getTransformedTime(timestamp) {
    const timePart = timestamp.split('_')[1];

    const hours = timePart.slice(0, 2);
    const minutes = timePart.slice(2, 4);
    const seconds = timePart.slice(4, 6);

    const formattedTime = `${hours}:${minutes}:${seconds}`;
    return `${formattedTime}`;
}
function getTransformedTimeWithoutSeconds(timestamp) {
    const timePart = timestamp.split('_')[1];

    const hours = timePart.slice(0, 2);
    const minutes = timePart.slice(2, 4);

    const formattedTime = `${hours}:${minutes}`;
    return `${formattedTime}`;
}