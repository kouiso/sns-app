import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, View } from 'react-native';

// これから作る SNS の、いちばん最初の画面。
// ここに書いた文字が、そのまま手元の端末に出る。
export default function App() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>はじめての画面</Text>
      <Text style={styles.body}>ここから SNS を作っていきます</Text>
      <Text style={styles.note}>いま書き換えたところが、すぐここに出ます</Text>
      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
  },
  body: {
    fontSize: 16,
    marginTop: 8,
    color: '#555',
  },
  note: {
    fontSize: 14,
    marginTop: 24,
    color: '#0a7',
  },
});
